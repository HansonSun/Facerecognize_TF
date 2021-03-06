import tensorflow as tf
import tensorflow.contrib.slim as slim


def inference(inputs,
              phase_train=True,
              keep_probability=0.5,
              weight_decay=0.0,
              feature_length=128,
              scope='vgg_16',
              w_init=slim.xavier_initializer_conv2d(uniform=True)):
    end_points={}
    with tf.variable_scope(scope, 'vgg_19', [inputs]):
        with slim.arg_scope([slim.conv2d, slim.fully_connected],
                            weights_initializer=w_init,
                            weights_regularizer=slim.l2_regularizer(weight_decay)):

            net = slim.repeat(inputs, 2, slim.conv2d, 64, [3, 3], scope='conv1')
            net = slim.max_pool2d(net, [2, 2], scope='pool1')
            net = slim.repeat(net, 2, slim.conv2d, 128, [3, 3], scope='conv2')
            net = slim.max_pool2d(net, [2, 2], scope='pool2')
            net = slim.repeat(net, 4, slim.conv2d, 256, [3, 3], scope='conv3')
            net = slim.max_pool2d(net, [2, 2], scope='pool3')
            net = slim.repeat(net, 4, slim.conv2d, 512, [3, 3], scope='conv4')
            net = slim.max_pool2d(net, [2, 2], scope='pool4')
            net = slim.repeat(net, 4, slim.conv2d, 512, [3, 3], scope='conv5')
            net = slim.max_pool2d(net, [2, 2], scope='pool5')
            # Use conv2d instead of fully_connected layers.
            net = slim.fully_connected(net, 4096,scope='fc6')
            net = slim.dropout(net, feature_length, is_training=phase_train,
                             scope='dropout6')
            net = slim.fully_connected(net, bottleneck_layer_size,  scope='fc7')
            net = slim.dropout(net, feature_length, is_training=phase_train,
                             scope='dropout7')

            return net, end_points
