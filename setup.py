import os
from setuptools import setup
from glob import glob

package_name = 'vortex_pyqt_gui'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    py_modules=['vortex_pyqt_gui.gui_layout'],
    maintainer='GUI',
    maintainer_email='eirisak@stud.ntnu.no',
    description='First draft for an AUV GUI, Vortex',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'Vortex_Gui_Node = vortex_pyqt_gui.main:main',
        ],
    },
)
