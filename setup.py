from distutils.core import setup

setup(
    name='dashcam',
    version='0.1.0',
    description='Raspberry Pi dashcam.',
    author='Zachary Huff',
    author_email='zach.huff.386@gmail.com',
    url='http://zachhuff386.github.io/dashcam',
    keywords='raspberry, pi, rpi, dashcam',
    packages=['dashcam'],
    license='GPL3',
    data_files=[
        ('/etc', ['data/etc/dashcam.conf']),
        ('/etc/systemd/system', ['data/systemd/dashcamd.service']),
        ('/usr/share/dashcam', ['data/share/beep.ogg']),
        ('bin', ['data/bin/dashcam']),
        ('bin', ['build/dashcam-stream']),
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Topic :: Multimedia :: Graphics :: Capture',
    ],
)
