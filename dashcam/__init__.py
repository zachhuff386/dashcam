import subprocess
import logging
import os
import time
import signal
import threading
import fnmatch

PYGAME_AVAILABLE = False
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    logging.debug('Pygame not aviable')

RPI_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    RPI_AVAILABLE = True
except ImportError:
    logging.debug('RPi.GPIO not aviable')

BBIO_AVAILABLE = False
try:
    import BBIO.GPIO as GPIO
    BBIO_AVAILABLE = True
except ImportError:
    logging.debug('BBIO.GPIO not aviable')

class DashCam:
    def __init__(self,
            input_device,
            input_media_type,
            input_width,
            input_height,
            input_frame_rate=None,
            input_device_delay=None,
            output_path=None,
            output_muxer=None,
            output_segment_length=None,
            stream_state_path=None,
            min_free_space=None,
            volume_level=None,
            light_gpio_pin=None,
            log_file=None,
            debug=None,
            v4l2_ctrls=None):
        self._running = False
        self._stream_state = False
        self._light_state = False
        self._stream_proc = None
        self._log_file = None

        if input_frame_rate is None:
            input_frame_rate = 30
        if input_device_delay is None:
            input_device_delay = 10000
        if output_path is None:
            output_path = 'dashcam_%i.avi'
        if output_muxer is None:
            output_muxer = 'avimux'
        if output_segment_length is None:
            output_segment_length = 300
        if stream_state_path is None:
            stream_state_path = '/var/run/dashcam_stream_state'

        self._input_device = input_device
        self._input_media_type = input_media_type
        self._input_device_delay = input_device_delay
        self._input_width = input_width
        self._input_height = input_height
        self._input_frame_rate = input_frame_rate
        self._output_muxer = output_muxer
        self._output_segment_length = output_segment_length
        self._output_segment_counter = None
        self._output_path = output_path
        self._stream_state_path = stream_state_path
        self._min_free_space = min_free_space
        self._volume_level = volume_level
        self._light_gpio_pin = light_gpio_pin
        self._log_file = log_file
        self._debug = debug
        self._v4l2_ctrls = v4l2_ctrls

        if PYGAME_AVAILABLE and self._volume_level:
            pygame.init()
            pygame.mixer.music.load('/usr/share/dashcam/beep.ogg')
            pygame.mixer.music.set_volume(self._volume_level)

        # Setup GPIO of aviable
        if self._light_gpio_pin:
            try:
                int(self._light_gpio_pin)
                if RPI_AVAILABLE:
                    self._setup_rpi_gpio()
                elif BBIO_AVAILABLE:
                    self._setup_bbio_gpio()
            except ValueError:
                if BBIO_AVAILABLE:
                    self._setup_bbio_gpio()

        # Prase output path
        self._parse_output_path()

        logging.info('Stream initialized')

        self._play_sound()
        time.sleep(0.2)
        self._play_sound()
        time.sleep(0.2)

    def __del__(self):
        self.stop()

    def _parse_output_path(self):
        if '%' not in self._output_path:
            logging.error(('Output path %s is invalid, %s formatters ' + \
                'must be in string.') % (self._output_path, '%'))
            exit(-1)

        if self._output_path[0] == '%':
            logging.error(('Output path %s is invalid, first character ' + \
                'cannot be %.') % (self._output_path, '%'))
            exit(-1)

        if not os.path.isdir(os.path.dirname(self._output_path)):
            logging.error('Output path %s does not exist.' % self._output_path)
            return

        if '%i' not in self._output_path:
            return

        if os.path.splitext(self._output_path)[0][-2:] != '%i':
            logging.error(('Output path %s is invalid, %s must be at ' + \
                'end of filename.') % (self._output_path, '%i'))
            exit(-1)
        if os.path.splitext(self._output_path)[0][-4] == '%':
            logging.error(('Output path %s is invalid, %s must be ' + \
                'seperated from other %s formaters.') % (
                self._output_path, '%i', '%'))
            exit(-1)
        if os.path.splitext(self._output_path)[0][-3].isdigit():
            logging.error(('Output path %s is invalid, %s cannot ' + \
                'be preceded by a number.') % (self._output_path, '%i'))
            exit(-1)

        path = os.path.dirname(self._output_path)
        basename = os.path.basename(self._output_path)
        suffix = basename[:basename.find('%')]
        index_sperator = os.path.splitext(self._output_path)[0][-3]
        index = 0

        # Get index of last file
        for filename in reversed(sorted(os.listdir(path))):
            base, ext = os.path.splitext(filename)
            if not fnmatch.fnmatch(filename, '%s*%s' % (suffix, ext)):
                continue
            try:
                index = int(base[base.rfind(index_sperator) + 1:]) + 1
            except ValueError:
                pass
            break

        self._output_segment_counter = index

    def _get_free_space(self):
        try:
            stat = os.statvfs(os.path.dirname(self._output_path))
            return float(stat.f_bavail) / stat.f_blocks
        except OSError:
            logging.error('Failed to get free space for %s directory.' % (
                os.path.dirname(self._output_path)))
            return 1

    def _open_log_file(self):
        if not isinstance(self._log_file, basestring):
            return
        logging.debug('Open process log file')
        self._log_file = open(self._log_file, 'a')

    def _read_stream_state(self):
        try:
            with open(self._stream_state_path) as state_file:
                if state_file.read().strip() == '1':
                    self.set_stream_state(True)
                else:
                    self.set_stream_state(False)
        except IOError:
            self.set_stream_state(False)

    def _remove_stream_state(self):
        try:
            logging.debug('Removing previous stream state file')
            os.remove(self._stream_state_path)
        except OSError:
            pass

    def _play_sound(self):
        if not PYGAME_AVAILABLE or not self._volume_level:
            return
        pygame.mixer.music.play()

    def _generate_proc_args(self):
        args = []

        args.append('dashcam-stream')

        # If input_device is none auto select first video device
        args.append('--device')
        args.append(str(self._input_device))

        args.append('--media-type')
        args.append(str(self._input_media_type))

        args.append('--muxer-name')
        args.append(str(self._output_muxer))

        args.append('--output-path')
        args.append(str(self._output_path).replace('%i', '%04i'))

        args.append('--dev-delay')
        args.append(str(self._input_device_delay))

        args.append('--stream-state-path')
        args.append(str(self._stream_state_path))

        args.append('--width')
        args.append(str(self._input_width))

        args.append('--height')
        args.append(str(self._input_height))

        args.append('--framerate')
        args.append(str(self._input_frame_rate))

        args.append('--segment-length')
        args.append(str(self._output_segment_length))

        if self._output_segment_counter:
            args.append('--segment-counter')
            args.append(str(self._output_segment_counter))

        return args

    def _apply_v4l2_ctrls(self):
        if not self._v4l2_ctrls:
            return

        for ctrl_name in self._v4l2_ctrls:
            ctrl_value = self._v4l2_ctrls[ctrl_name]
            args = [
                'v4l2-ctl',
                '--device',
                self._input_device,
                '--set-ctrl',
                '%s=%s' % (ctrl_name, ctrl_value),
            ]

            try:
                subprocess.check_output(args)
            except CalledProcessError:
                logging.exception('Failed to set v4l2-ctl %s' % ctrl_name)

    def _setup_rpi_gpio(self):
        try:
            self._light_gpio_pin = int(self._light_gpio_pin)
        except ValueError:
            self._light_gpio_pin = None
            logging.error('Light GPIO pin must be int, LED disabled.')
            return
        # Save refrence to function for __del__
        self._gpio_cleanup = GPIO.cleanup
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self._light_gpio_pin, GPIO.OUT)
        logging.info('RPi.GPIO initialized')

    def _setup_bbio_gpio(self):
        if not isinstance(self._light_gpio_pin, basestring):
            self._light_gpio_pin = None
            logging.error('Light GPIO pin must be string, LED disabled.')
            return
        # Save refrence to function for __del__
        self._gpio_cleanup = GPIO.cleanup
        GPIO.setup(self._light_gpio_pin, GPIO.OUT)
        logging.info('BBIO.GPIO initialized')

    def _prune_segments_thread(self):
        logging.debug('Prune segments thread started.')
        while self._running:
            self.prune_segments()
            time.sleep(1)
        logging.debug('Exiting prune segments thread...')

    def prune_segments(self):
        path = os.path.dirname(self._output_path)
        basename = os.path.basename(self._output_path)
        suffix = basename[:basename.find('%')]

        while self._get_free_space() < self._min_free_space:
            for filename in sorted(os.listdir(path)):
                base, ext = os.path.splitext(filename)
                if not fnmatch.fnmatch(filename, '%s*%s' % (suffix, ext)):
                    continue
                file_path = os.path.join(path, filename)
                logging.info('Pruning segment %s.' % file_path)

                try:
                    os.remove(file_path)
                    break
                except OSError:
                    logging.error('Failed to remove file %s, skipping...' % (
                        file_path))

    def set_light_state(self, state):
        if (not RPI_AVAILABLE and not BBIO_AVAILABLE) or \
                not self._light_gpio_pin or \
                self._light_state is state:
            return
        logging.debug('Light state: %s' % state)
        self._light_state = state
        GPIO.output(self._light_gpio_pin, state)

    def get_light_state(self):
        return self._light_state

    def set_stream_state(self, state):
        if self._stream_state is state:
            return
        logging.info('Stream state: %s' % state)
        self._stream_state = state
        self.set_light_state(state)
        self.on_stream_state(state)

    def get_stream_state(self, state):
        return self._stream_state

    def on_stream_state(self, state):
        if state:
            logging.info('Stream started')
        else:
            logging.info('Stream stopped')

    def start_stream_proc(self):
        self._remove_stream_state()
        self.set_stream_state(False)

        # Check for webcam
        if not os.access(self._input_device, os.R_OK):
            logging.warning('Video device %s does not exist, waiting...' % (
                self._input_device))
            return

        logging.info('Starting stream process')
        self._open_log_file()
        self._apply_v4l2_ctrls()
        self._stream_proc = subprocess.Popen(self._generate_proc_args(),
            stdin=subprocess.PIPE, stdout=self._log_file,
            stderr=self._log_file)

    def stop_stream_proc(self):
        if not self._stream_proc:
            return
        logging.info('Stopping stream process')
        self._stream_proc.send_signal(signal.SIGINT)

    def wait_stream_proc(self):
        if not self._stream_proc:
            return
        logging.info('Waiting for stream process')
        self._stream_proc.wait()
        self._remove_stream_state()

    def poll_stream_proc(self):
        if not self._stream_proc:
            return 0
        returncode = self._stream_proc.poll()
        if returncode is not None:
            logging.info('Stream process ended with exit code %s' % (
                self._stream_proc.returncode))
        return returncode

    def start(self):
        if self._running:
            raise TypeError('Dashcam is already running.')
        self._running = True

        if self._min_free_space:
            threading.Thread(target=self._prune_segments_thread).start()

        while self._running:
            if self.poll_stream_proc() is not None:
                self.start_stream_proc()
            self._read_stream_state()
            time.sleep(0.1)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if RPI_AVAILABLE or BBIO_AVAILABLE:
            logging.debug('Cleaning up GPIO...')
            self._gpio_cleanup()
        logging.info('Exiting...')
        self.stop_stream_proc()
        self.wait_stream_proc()
