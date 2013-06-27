import subprocess
import signal
import time
import os

# Global Settings
INPUT_DEVICE = '/dev/video0'
INPUT_MEDIA_TYPE = 'video/x-h264'
INPUT_WIDTH = 1920
INPUT_HEIGHT = 1080
INPUT_FRAME_RATE = 30
OUTPUT_PATH = './'
OUTPUT_SEGMENT_LENGTH = 10
VOLUME_LEVEL = 0.10
FOCUS_STEP = 10

AUDIO_AVAILABLE = False
try:
    import pygame
    try:
        pygame.init()
        pygame.mixer.music.load('beep.ogg')
        pygame.mixer.music.set_volume(VOLUME_LEVEL)
        AUDIO_AVAILABLE = True
    except pygame.error:
        pass
except ImportError:
    pass

numbers = [
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
    [''] * 6,
]

numbers[0][0] = '   ___  '
numbers[0][1] = '  / _ \\ '
numbers[0][2] = ' | | | |'
numbers[0][3] = ' | | | |'
numbers[0][4] = ' | |_| |'
numbers[0][5] = '  \\___/ '

numbers[1][0] = '  __ '
numbers[1][1] = ' /_ |'
numbers[1][2] = '  | |'
numbers[1][3] = '  | |'
numbers[1][4] = '  | |'
numbers[1][5] = '  |_|'

numbers[2][0] = '  ___  '
numbers[2][1] = ' |__ \\ '
numbers[2][2] = '    ) |'
numbers[2][3] = '   / / '
numbers[2][4] = '  / /_ '
numbers[2][5] = ' |____|'

numbers[3][0] = '  ____  '
numbers[3][1] = ' |___ \\ '
numbers[3][2] = '   __) |'
numbers[3][3] = '  |__ < '
numbers[3][4] = '  ___) |'
numbers[3][5] = ' |____/ '

numbers[4][0] = '  _  _   '
numbers[4][1] = ' | || |  '
numbers[4][2] = ' | || |_ '
numbers[4][3] = ' |__   _|'
numbers[4][4] = '    | |  '
numbers[4][5] = '    |_|  '

numbers[5][0] = '  _____ '
numbers[5][1] = ' | ____|'
numbers[5][2] = ' | |__  '
numbers[5][3] = ' |___ \\ '
numbers[5][4] = '  ___) |'
numbers[5][5] = ' |____/ '

numbers[6][0] = '    __  '
numbers[6][1] = '   / /  '
numbers[6][2] = '  / /_  '
numbers[6][3] = ' | \'_ \\ '
numbers[6][4] = ' | (_) |'
numbers[6][5] = '  \\___/ '

numbers[7][0] = '  ______ '
numbers[7][1] = ' |____  |'
numbers[7][2] = '     / / '
numbers[7][3] = '    / /  '
numbers[7][4] = '   / /   '
numbers[7][5] = '  /_/    '

numbers[8][0] = '   ___  '
numbers[8][1] = '  / _ \\ '
numbers[8][2] = ' | (_) |'
numbers[8][3] = '  > _ < '
numbers[8][4] = ' | (_) |'
numbers[8][5] = '  \\___/ '

numbers[9][0] = '   ___  '
numbers[9][1] = '  / _ \\ '
numbers[9][2] = ' | (_) |'
numbers[9][3] = '  \\__, |'
numbers[9][4] = '    / / '
numbers[9][5] = '   /_/  '

line_break = '#################################################'
start_time = int(time.time())

def print_start():
    print line_break
    print '   _____   _______              _____    _______'
    print '  / ____| |__   __|     /\\     |  __ \\  |__   __|'
    print ' | (___      | |       /  \\    | |__) |    | |'
    print '  \\___ \\     | |      / /\\ \\   |  _  /     | |'
    print '  ____) |    | |     / ____ \\  | | \\ \\     | |'
    print ' |_____/     |_|    /_/    \\_\\ |_|  \\_\\    |_|'
    print ''

def print_stop():
    print line_break
    print '   _____   _______    ____    _____'
    print '  / ____| |__   __|  / __ \\  |  __ \\'
    print ' | (___      | |    | |  | | | |__) |'
    print '  \\___ \\     | |    | |  | | |  ___/'
    print '  ____) |    | |    | |__| | | |'
    print ' |_____/     |_|     \\____/  |_|'
    print ''
    print line_break

def print_stop():
    print line_break
    print '   _____   _______    ____    _____'
    print '  / ____| |__   __|  / __ \\  |  __ \\'
    print ' | (___      | |    | |  | | | |__) |'
    print '  \\___ \\     | |    | |  | | |  ___/'
    print '  ____) |    | |    | |__| | | |'
    print ' |_____/     |_|     \\____/  |_|'
    print ''
    print line_break

def print_error():
    print line_break
    print '  ______   _____    _____     ____    _____'
    print ' |  ____| |  __ \\  |  __ \\   / __ \\  |  __ \\'
    print ' | |__    | |__) | | |__) | | |  | | | |__) |'
    print ' |  __|   |  _  /  |  _  /  | |  | | |  _  /'
    print ' | |____  | | \\ \\  | | \\ \\  | |__| | | | \\ \\'
    print ' |______| |_|  \\_\\ |_|  \\_\\  \\____/  |_|  \\_\\'
    print ''
    print line_break
    exit()

def print_num(num):
    num = str(num)
    lines = [''] * 6

    for line_num in xrange(6):
        for digit in num:
            digit = int(digit)
            lines[line_num] += numbers[digit][line_num]

    print line_break
    for line_num in xrange(6):
        print lines[line_num]
    print ''

def v4l2_set_ctrl(name, value):
    args = [
        'v4l2-ctl',
        '--device',
        INPUT_DEVICE,
        '--set-ctrl',
        '%s=%s' % (name, value),
    ]
    subprocess.check_output(args)

def gst_record(focus_value):
    proc = None
    try:
        filename = os.path.join(OUTPUT_PATH, '%s_%s.avi' % (
            start_time, focus_value))

        v4l2_set_ctrl('focus_absolute', focus_value)

        args = ('gst-launch-1.0 -e ' + \
            'v4l2src device=%s ! %s,width=%s,height=%s,framerate=%s/1 ! ' + \
            'queue ! avimux ! filesink location=%s') % (
                INPUT_DEVICE, INPUT_MEDIA_TYPE, INPUT_WIDTH,
                INPUT_HEIGHT, INPUT_FRAME_RATE, filename)

        proc = subprocess.Popen(args, shell=True)

        end_time = time.time() + OUTPUT_SEGMENT_LENGTH

        while time.time() < end_time:
            if proc.poll() is not None:
                print 'Gstreamer exited with error %s' % proc.returncode
                print_error()
    finally:
        if proc:
            proc.send_signal(signal.SIGINT)
            proc.wait()

print_start()
v4l2_set_ctrl('focus_auto', '0')
for i in xrange((250 / FOCUS_STEP) + 1):
    focus = i * FOCUS_STEP
    print_num(focus)
    gst_record(focus)
    if AUDIO_AVAILABLE:
        pygame.mixer.music.play()
print_stop()
