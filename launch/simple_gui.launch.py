from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    ld = LaunchDescription()

    Vortex_Gui_Node = Node(
        package = 'vortex_pyqt_gui',
        executable='Vortex_Gui_Node',
    )

    ld.add_action(Vortex_Gui_Node)

    return ld