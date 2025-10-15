import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Int32, String

class AUVDataSubscriber(Node):
    def __init__(self):
        super().__init__('auv_data_subscriber')
        self.latest_float = None
        self.latest_int = None
        self.latest_string = None

        self.create_subscription(Float32, '/FloatTopic', self.float_callback, 10)
        self.create_subscription(Int32, '/IntTopic', self.int_callback, 10)
        self.create_subscription(String, '/StringTopic', self.string_callback, 10)

    def float_callback(self, msg):
        self.latest_float = msg.data

    def int_callback(self, msg):
        self.latest_int = msg.data

    def string_callback(self, msg):
        self.latest_string = msg.data