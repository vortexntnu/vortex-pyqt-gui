import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Int32, String
from sensor_msgs.msg import Image

from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

from cv_bridge import CvBridge
import cv2

class AUVDataSubscriber(Node):
    def __init__(self, ui):
        super().__init__('auv_data_subscriber')
        self.ui = ui

        # initialize CvBridge
        self.bridge = CvBridge()

        # Initialize variables for subscriptions
        self.latest_float = None
        self.latest_int = None
        self.latest_string = None
        self.latest_cam_rgb_image = None

        # Create subscriptions
        self.create_subscription(Float32, '/FloatTopic', self.float_callback, 10)
        self.create_subscription(Int32, '/IntTopic', self.int_callback, 10)
        self.create_subscription(String, '/StringTopic', self.string_callback, 10)
        self.cam_image_color_subscription = self.create_subscription(Image, '/cam/image_color', self.cam_image_color_callback, 10)
        self.cam_down_image_color_subscription = self.create_subscription(Image, '/cam_down/image_color', self.cam_down_image_color_callback, 10)

    # Define callbacks for subscriptions
    def float_callback(self, msg):
        self.latest_float = msg.data

    def int_callback(self, msg):
        self.latest_int = msg.data

    def string_callback(self, msg):
        self.latest_string = msg.data
    
    def cam_image_color_callback(self, msg):
        try:
            # Convert ROS Image → OpenCV (BGR)
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Convert OpenCV (BGR) → RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            if rgb_image is None:
                return  # no frame yet

            # Convert numpy array to QImage
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            # Scale the image to fit the label while keeping aspect ratio
            pixmap = QPixmap.fromImage(qt_image).scaled(self.ui.camLabel.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio)

            # Update the QLabel
            self.ui.camLabel.setPixmap(pixmap)

        except Exception as e:
            self.get_logger().error(f"Image conversion failed: {e}")
    
    def cam_down_image_color_callback(self, msg):
        try:
            # Convert ROS Image → OpenCV (BGR)
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Convert OpenCV (BGR) → RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            if rgb_image is None:
                return  # no frame yet

            # Convert numpy array to QImage
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            # Scale the image to fit the label while keeping aspect ratio
            pixmap = QPixmap.fromImage(qt_image).scaled(self.ui.camDownLabel.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio)
            
            # Update the QLabel
            self.ui.camDownLabel.setPixmap(pixmap)

        except Exception as e:
            self.get_logger().error(f"Image conversion failed: {e}")