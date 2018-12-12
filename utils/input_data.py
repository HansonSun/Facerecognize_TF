from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import cv2
import tensorflow as tf
import os,sys
sys.path.append("../")
import faceutils as fu
import config
import matplotlib.pyplot as plt
import math


def text_parse_function(imgpath, label):
	value=tf.read_file(imgpath)
	img=tf.image.decode_jpeg(value,channels=3)
	print (img)
	img = tf.image.resize_images(img, [config.dataset_img_width,config.dataset_img_height])
	print (img)
	#blur the image 
	if config.blur_image==1:
		blur_size=tf.random_uniform([], 1+config.dataset_img_width*config.blur_ratio_range[0], 1+config.dataset_img_height*config.blur_ratio_range[1])
		img = tf.image.resize_images(img, [blur_size,blur_size])
		img = tf.image.resize_images(img, [config.dataset_img_width,config.dataset_img_height])

	#random crop the image
	if config.random_crop==1:
		assert (config.crop_img_height<config.dataset_img_height and config.crop_img_width<config.dataset_img_width)
		img = tf.random_crop(img, [config.crop_img_height,config.crop_img_width,3])

	#random the image
	if config.random_flip==1:
		img = tf.image.random_flip_left_right(img)

	#random rotate the image
	if config.random_rotate==1:
		img=tf.contrib.image.rotate(img,tf.random_uniform([], math.pi*config.rotate_angle_range[0]/180.0,math.pi*config.rotate_angle_range[1]/180.0 ))

	#random color brightness
	if config.random_color_brightness==1:	
		img=tf.image.adjust_brightness(img, tf.random_uniform([], config.brightness_range[0], config.brightness_range[1]))

	#random color saturation
	if config.random_color_saturation==1:
		img=tf.image.random_saturation(img,lower=config.saturaton_range[0],upper=config.saturaton_range[1])

	#random color hue
	if config.random_color_hue==1:
		img=tf.image. adjust_hue(img, tf.random_uniform([],config.hue_range[0], config.hue_range[1]))

	#random color contrast
	if config.random_color_contrast==1:
		img=tf.image.random_contrast(img,lower=config.contrast_range[0],upper=config.contrast_range[1])

	if config.input_test_flag==0:
		img = tf.cast(img, tf.float32)
		# standardize the image
		if config.img_preprocess_type==0:
			img=tf.image.per_image_standardization(img)
		elif config.img_preprocess_type==1:
			img = tf.subtract(img,127.5)
			img=tf.div(img,128.0)
		elif config.process_type==2:
			img=tf.div(img,255.0)

	return img, label

def tfrecord_parse_function(example_proto):
	features = {'image_raw': tf.FixedLenFeature([], tf.string),'label': tf.FixedLenFeature([], tf.int64)}
	features = tf.parse_single_example(example_proto, features)
	# You can do more image distortion here for training data
	img = tf.image.decode_jpeg(features['image_raw'])
	img = tf.reshape(img, shape=(112,112,3))
	r, g, b = tf.split(img, num_or_size_splits=3, axis=-1)
	img = tf.concat([b, g, r], axis=-1)

	#resize the image
	img = tf.py_func(resize_image, [img,config.dataset_img_width,config.dataset_img_height], tf.uint8)
	#random crop the image
	if config.random_crop==1:
		if config.crop_img_height>config.dataset_img_height or config.crop_img_width>config.dataset_img_width:
			print ("crop size must <= input size")
			exit()
		img = tf.random_crop(img, [config.crop_img_height,config.crop_img_width,3])

	#random the image
	if config.random_flip==1:
		img = tf.image.random_flip_left_right(img)

	#random rotate the image
	if config.random_rotate==1:
		img = tf.py_func(random_rotate_image, [img,config.rotate_angle_range[0],config.rotate_angle_range[1]], tf.uint8)

	#random color brightness
	if config.random_color_brightness==1:
		img=tf.image.random_brightness(img,config.max_brightness)

	#random color saturation
	if config.random_color_saturation==1:
		img=tf.image.random_saturation(img,lower=config.saturaton_range[0],upper=config.saturaton_range[1])

	#random color hue
	if config.random_color_hue==1:
		img=tf.image.random_hue(img,config.max_hue)

	#random color contrast
	if config.random_color_contrast==1:
		img=tf.image.random_contrast(img,lower=config.contrast_range[0],upper=config.contrast_range[1])

	if config.input_test_flag==0:
		img = tf.cast(img, tf.float32)
		# standardize the image
		if config.normtype==0:
			img=tf.image.per_image_standardization(img)
		elif config.normtype==1:
			img = tf.subtract(img,127.5)
			img = tf.div(img,128.0)
		elif config.normtype==2:
			img = tf.div(img,255.0)

	label = tf.cast(features['label'], tf.int64)
	return img, label

def input_images_data(dataset_path,batch_size):
	img_dataset=fu.dataset.ImageDatasetReader([dataset_path])
	img_paths,labels=img_dataset.paths_and_labels()
	dataset=tf.data.Dataset.from_tensor_slices((img_paths,labels))
	dataset = dataset.map(text_parse_function,num_parallel_calls=4)
	dataset = dataset.shuffle(buffer_size=5000)
	dataset = dataset.batch(batch_size)
	iterator = dataset.make_initializable_iterator()
	next_element = iterator.get_next()
	config.nrof_classes=img_dataset.total_identity
	return iterator,next_element

def input_tfrecord_data(record_path,batch_size):
	record_dataset = tf.data.TFRecordDataset(record_path)
	record_dataset = record_dataset.map(tfrecord_parse_function)
	record_dataset = record_dataset.shuffle(buffer_size=5000)
	record_dataset = record_dataset.batch(batch_size)
	iterator = record_dataset.make_initializable_iterator()
	next_element = iterator.get_next()
	return iterator,next_element,_


def read_images_test():
	config.input_test_flag=1
	iterator,next_element=input_images_data("/home/hanson/dataset/test2",batch_size=1)
	sess = tf.Session()

	for i in range(100):
		sess.run(iterator.initializer)
		while True:
			try:
				images, labels = sess.run(next_element)
				print (labels )
				resultimg=images[0]
				resultimg=resultimg.astype(np.uint8)
				#plt.show()
				resultimg=cv2.cvtColor(resultimg,cv2.COLOR_RGB2BGR)
				cv2.imshow('test', resultimg)
				cv2.waitKey(0)

			except tf.errors.OutOfRangeError:
				print("End of dataset")
				break


def read_tfrecord_test():
	config.input_test_flag=1
	iterator,next_element=tfrecord_input_data('tfrecord_dataset/ms1m_train.tfrecords',1)
	sess = tf.Session()

	# begin iteration
	for i in range(1000):
		sess.run(iterator.initializer)
		while True:
			try:
				images, labels = sess.run(next_element)
				print (labels )
				cv2.imshow('test', images[0])
				cv2.waitKey(0)
				
			except tf.errors.OutOfRangeError:
				print("End of dataset")


if __name__ == '__main__':
	read_images_test()