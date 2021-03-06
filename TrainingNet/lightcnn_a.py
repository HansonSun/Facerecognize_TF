import tensorflow as tf
import tensorflow.contrib.slim as slim


def MFM(net):
	net_channel=int (net.shape[-1])
	#Slice
	slice1,slice2 = tf.split(net,[net_channel/2,net_channel/2],int(net.shape.ndims)-1 )
	#eltwise max
	eltwise=tf.maximum(slice1,slice2)
	return eltwise

def inference(image,phase_train=True,feature_length=128,weight_decay=5e-5):
	with slim.arg_scope([slim.conv2d, slim.fully_connected],activation_fn=None,
					weights_initializer=slim.xavier_initializer_conv2d(uniform=True),
					weights_regularizer=slim.l2_regularizer(0.1)):
		#conv1
		net=slim.conv2d(image,96,[9,9],stride=1,scope="conv1",padding="SAME")
		#MFM1
		net=MFM(net)
		#pool1
		net=slim.max_pool2d(net,[2,2],stride=2,scope="pool1")
		#conv2
		net=slim.conv2d(net,192,[5,5],stride=1,scope="conv2",padding="SAME")
		#MFM2
		net=MFM(net)
		#pool2
		net=slim.max_pool2d(net,[2,2],stride=2,scope="pool2")
		#conv3
		net=slim.conv2d(net,256,[5,5],stride=1,scope="conv3",padding="SAME")
		#MFM3
		net=MFM(net)
		#pool3
		net=slim.max_pool2d(net,[2,2],stride=2,scope="pool3")
		#conv4
		net=slim.conv2d(net,384,[4,4],stride=1,scope="conv4",padding="SAME")
		#MFM4
		net=MFM(net)
		#pool4
		net=slim.max_pool2d(net,[2,2],stride=2,scope="pool4")
		#fc1
		net=slim.flatten(net)
		net=slim.fully_connected(net,512,activation_fn=None)
		#MFM_FC1
		net=MFM(net)

	return net
