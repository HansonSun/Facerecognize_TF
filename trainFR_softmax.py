from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import sys
sys.path.append("/home/hanson/facetools")
sys.path.append("TrainingNet")
sys.path.append("TrainingLoss")
import numpy as np
import tensorflow as tf
import importlib
import config
import tensorflow.contrib.slim as slim
import time
from datetime import datetime
from utils.benchmark_validate import *
import shutil
import faceutils as fu
from  utils.input_dataset import TFRecordDataset



class trainFR():
    def __init__(self):
        #1. load config file
        self.conf=config.get_config()
        #2. create log and model saved dir according to the datetime
        subdir = datetime.strftime(datetime.now(), '%Y%m%d-%H%M%S')
        self.models_dir = os.path.join("saved_models", subdir, "models")
        if not os.path.isdir(self.models_dir):  # Create the model directory if it doesn't exist
            os.makedirs(self.models_dir)
        self.logs_dir = os.path.join("saved_models", subdir, "logs")
        if not os.path.isdir(self.logs_dir):  # Create the log directory if it doesn't exist
            os.makedirs(self.logs_dir)
        self.topn_models_dir = os.path.join("saved_models", subdir, "topn")#topn dir used for save top accuracy model
        if not os.path.isdir(self.topn_models_dir):  # Create the topn model directory if it doesn't exist
            os.makedirs(self.topn_models_dir)
        
        #3. load dataset
        if self.conf.use_tfrecord:
            self.inputdataset=TFRecordDataset(self.conf)
        else:
            self.inputdataset=fu.TFImageDataset(self.conf)
            
            

        self.traindata_iterator,self.traindata_next_element=self.inputdataset.generateDataset( )
        self.nrof_classes=self.inputdataset.nrof_classes


    def make_model(self):
        #2.load dataset and define placeholder
        self.phase_train  = tf.placeholder(tf.bool, name='phase_train')
        self.images_input = tf.placeholder(name='input', shape=[None, self.conf.input_img_height,self.conf.input_img_width, 3], dtype=tf.float32)
        self.labels_input = tf.placeholder(name='labels', shape=[None, ], dtype=tf.int64)

        #3.load model and inference
        network = importlib.import_module(self.conf.fr_model_def)
        print ("trianing network:%s"%self.conf.fr_model_def)
        print ("input image [ height:%d width:%d channel:%d ]"%(self.conf.input_img_height,self.conf.input_img_width,3))

        self.prelogits = network.inference(
            self.images_input,
            dropout_keep_prob=0.8,
            phase_train=self.phase_train,
            weight_decay=self.conf.weight_decay,
            feature_length=self.conf.feature_length)
    
    def summary(self):

        #add grad histogram op
        for grad, var in self.grads:
            if grad is not None:
                tf.summary.histogram(var.op.name + '/gradients', grad)

        #add trainabel variable gradients
        for var in tf.trainable_variables():
            tf.summary.histogram(var.op.name, var)

        #add loss summary
        tf.summary.scalar("softmax_loss",self.softmaxloss)
        tf.summary.scalar("total_loss",self.total_loss)
        tf.summary.scalar("learning_rate",self.learning_rate)

        self.summary_op = tf.summary.merge_all()

    def loss(self):
        logits = slim.fully_connected(self.prelogits,
                                      self.nrof_classes,
                                      activation_fn=None,
                                      weights_initializer=slim.initializers.xavier_initializer(),
                                      weights_regularizer=slim.l2_regularizer(5e-4),
                                      scope='Logits',
                                      reuse=False)
        self.softmaxloss = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=self.labels_input),name="loss")

        # Norm for the prelogits
        eps = 1e-4
        prelogits_norm = tf.reduce_mean(tf.norm(tf.abs(self.prelogits)+eps, ord=1, axis=1))
        tf.add_to_collection('losses', prelogits_norm * 5e-4)
        tf.add_to_collection('losses', self.softmaxloss)

        custom_loss=tf.get_collection("losses")
        regularization_losses = tf.get_collection(tf.GraphKeys.REGULARIZATION_LOSSES)
        self.total_loss=tf.add_n(custom_loss+regularization_losses,name='total_loss')



        embeddings = tf.nn.l2_normalize(self.prelogits, 1, 1e-10, name='embeddings')
        self.predict_labels=tf.argmax(logits,1)

        #adjust learning rate
        self.global_step = tf.Variable(0, trainable=False)
        if self.conf.lr_type=='exponential_decay':
            self.learning_rate = tf.train.exponential_decay(self.conf.learning_rate,
                                                            self.global_step,
                                                            self.conf.learning_rate_decay_step,
                                                            self.conf.learning_rate_decay_rate,
                                                            staircase=True)
        elif self.conf.lr_type=='piecewise_constant':
            self.learning_rate = tf.train.piecewise_constant(self.global_step, self.conf.boundaries, self.conf.values)
        elif self.conf.lr_type=='manual_modify':
            pass


        print ("lr stratege : %s"%self.conf.lr_type)


    def optimizer(self):
        if self.conf.optimizer=='ADAGRAD':
            opt = tf.train.AdagradOptimizer(self.learning_rate)
        elif self.conf.optimizer=='ADADELTA':
            opt = tf.train.AdadeltaOptimizer(self.learning_rate, rho=0.9, epsilon=1e-6)
        elif self.conf.optimizer=='ADAM':
            opt = tf.train.AdamOptimizer(self.learning_rate, beta1=0.9, beta2=0.999, epsilon=0.1)
        elif self.conf.optimizer=='RMSPROP':
            opt = tf.train.RMSPropOptimizer(self.learning_rate, decay=0.9, momentum=0.9, epsilon=1.0)
        elif self.conf.optimizer=='MOM':
            opt = tf.train.MomentumOptimizer(self.learning_rate, 0.9, use_nesterov=True)
        else:
            raise ValueError('Invalid optimization algorithm')
        print ("optimizer stratege : %s"%self.conf.optimizer)

        self.grads = opt.compute_gradients(self.total_loss)
        update_ops = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES)+tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
            apply_gradient_op = opt.apply_gradients(self.grads, global_step=self.global_step)


        variable_averages = tf.train.ExponentialMovingAverage(0.9999, self.global_step)
        variables_averages_op = variable_averages.apply(tf.trainable_variables())

        with tf.control_dependencies([apply_gradient_op, variables_averages_op]):
            self.train_op = tf.no_op(name='train')

        return self.train_op


    def process(self):
        saver=tf.train.Saver(tf.trainable_variables(),max_to_keep=2)

        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            sess.run(tf.local_variables_initializer())
            summary_writer=tf.summary.FileWriter(self.logs_dir,sess.graph)

            for epoch in range(self.conf.max_nrof_epochs):
                sess.run(self.traindata_iterator.initializer)
                while True:
                    use_time=0
                    try:
                        start_time=time.time()
                        images_train, labels_train = sess.run(self.traindata_next_element)
                        
                        input_dict={self.phase_train:True,self.images_input:images_train,self.labels_input:labels_train}
                        result_op=[self.train_op,self.global_step,self.learning_rate,self.total_loss,self.predict_labels,self.labels_input]
                        _,step,lr,train_loss,predict_labels,real_labels ,summary_str= sess.run(result_op+[self.summary_op],feed_dict=input_dict)
                        summary_writer.add_summary(summary_str, global_step=step)
                        end_time=time.time()
                        use_time+=(end_time-start_time)
                        train_acc=np.equal(predict_labels,real_labels).mean()

                        #display train result
                        if(step%self.conf.display_iter==0):
                            print ("step:%d lr:%f time:%.3f s total_loss:%.3f acc:%.3f epoch:%d"%(step,lr,use_time,train_loss,train_acc,epoch) )
                            use_time=0
                        
                        if (self.conf.save_iter!=-1 and step%self.conf.save_iter==0):
                            print ("save checkpoint")
                            filename_cpkt = os.path.join(self.models_dir, "%d.ckpt"%step)
                            saver.save(sess, filename_cpkt)

                        if (self.conf.test_iter!=-1 and step%self.conf.test_iter==0):
                            if self.conf.benchmark_dict["test_lfw"] :
                                acc_dict=test_benchmark(self.conf,self.models_dir)
                                if acc_dict["lfw_acc"]>self.conf.topn_threshold:
                                    with open(os.path.join(self.logs_dir,"topn_acc.txt"),"a+") as topn_file:
                                        topn_file.write("%s %s\n"%(os.path.join(self.topn_models_dir, "%d.ckpt"%step),str(acc_dict)) )
                                    shutil.copyfile(os.path.join(self.models_dir, "%d.ckpt.meta"%step),os.path.join(self.topn_models_dir, "%d.ckpt.meta"%step))
                                    shutil.copyfile(os.path.join(self.models_dir, "%d.ckpt.index"%step),os.path.join(self.topn_models_dir, "%d.ckpt.index"%step))
                                    shutil.copyfile(os.path.join(self.models_dir, "%d.ckpt.data-00000-of-00001"%step),os.path.join(self.topn_models_dir, "%d.ckpt.data-00000-of-00001"%step))
                            
                        
                    except tf.errors.OutOfRangeError:
                        print("End of epoch ")
                        break
    def run(self):
        self.make_model()
        self.loss()
        self.optimizer()
        self.summary()
        self.process()




if __name__=="__main__":
    fr=trainFR()
    fr.run()