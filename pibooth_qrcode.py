# -*- coding: utf-8 -*-

"""Pibooth plugin to display a QR Code on the screen during idle time."""

try:
    import qrcode
except ImportError:
    qrcode = None
    pass  # When running the setup.py, qrcode is not yet installed
import pygame
import pibooth
from pibooth.view.background import multiline_text_to_surfaces
from pibooth.utils import LOGGER
import signal

__version__ = "1.0.2"


SECTION = 'QRCODE'
LOCATIONS = ['topleft', 'topright',
             'bottomleft', 'bottomright',
             'midtop-left', 'midtop-right',
             'midbottom-left', 'midbottom-right']
TEXT_POSITIONS = ['left-right', 'top-bottom']


def dequote(text):
    # solve pibooth issue with quotes in cfg
    if (len(text)>1):
        if (text[0] == '"' and text[-1] == '"'):
            text = text[1:][:-1]
    return text


@pibooth.hookimpl
def pibooth_configure(cfg):
    """Declare the new configuration options"""
    cfg.add_option(SECTION, 'prefix_url', "{url}",
                   "URL which may be composed of variables: {picture}, {count}, {url}")
    cfg.add_option(SECTION, 'foreground', (255, 255, 255),
                   "Foreground color",
                   "Color", (255, 255, 255))
    cfg.add_option(SECTION, 'background', (0, 0, 0),
                   "Background color",
                   "Background color", (0, 0, 0))
    cfg.add_option(SECTION, 'side_text', "",
                   "Optional text displayed close to the QR code",
                   "Side text", "")
    cfg.add_option(SECTION, 'offset', (20, 40),
                   "Offset (x, y) from location")
    cfg.add_option(SECTION, 'wait_location', "bottomleft",
                   "Location on 'wait' state: {}".format(', '.join(LOCATIONS)),
                   "Location on wait screen", LOCATIONS)
    cfg.add_option(SECTION, 'print_location', "bottomright",
                   "Location on 'print' state: {}".format(', '.join(LOCATIONS)),
                   "Location on print screen", LOCATIONS)
    cfg.add_option(SECTION, 'size', "7",
                   "Size of QR code", "Pixel Size", "7")
    cfg.add_option(SECTION, 'border_size', "4",
                   "Size of QR code", "Border Size", "4")
    cfg.add_option(SECTION, 'text_position', "left-right",
                   "Position of text: {}".format(', '.join(TEXT_POSITIONS)),
                   "Position regarding to QR code", TEXT_POSITIONS)
 

def get_qrcode_rect(win_rect, qrcode_image, location, offset):
    sublocation = ''
    if '-' in location:
        location, sublocation = location.split('-')
    pos = list(getattr(win_rect, location))
    if 'top' in location:
        pos[1] += offset[1]
    else:
        pos[1] -= offset[1]
    if 'left' in location:
        pos[0] += offset[0]
    else:
        pos[0] -= offset[0]
    if 'mid' in location:
        if 'left' in sublocation:
            pos[0] -= qrcode_image.get_size()[0] // 2
        else:
            pos[0] += (qrcode_image.get_size()[0] // 2 + 2 * offset[0])
    qr_rect = qrcode_image.get_rect(**{location: pos})
    return qr_rect


def get_text_rect(win_rect, qrcode_rect, location, margin=10 , text_position='left-right'):
    text_rect = pygame.Rect(0, 0, win_rect.width // 6, qrcode_rect.height)
    sublocation = ''
    text_bottom = False
    if '-' in location:
        location, sublocation = location.split('-')
    if text_position == 'left-right':
        text_rect.top = qrcode_rect.top
        if 'left' in location:
            text_rect.left = qrcode_rect.right + margin
        else:
            text_rect.right = qrcode_rect.left - margin
        if 'mid' in location:
            if 'left' in sublocation:
                text_rect.right = qrcode_rect.left - margin
            else:
                text_rect.left = qrcode_rect.right + margin
    else:
        text_rect.left = qrcode_rect.left
        if 'top' in location:
            text_rect.top = qrcode_rect.bottom
            text_bottom = True
        else:
            text_rect.bottom = qrcode_rect.top
    return text_rect, text_bottom


def place_text(cfg, win_rect, qrcode_rect, location, win):
    side_text = dequote(cfg.get(SECTION, 'side_text'))
    if side_text:
        text_position = cfg.get(SECTION, 'text_position')
        text_rect, text_bottom = get_text_rect(win_rect, qrcode_rect, location, text_position=text_position)
        texts = multiline_text_to_surfaces(side_text,
                                           cfg.gettyped('WINDOW', 'text_color'),
                                           text_rect, 'bottom-left'
                                           )
        last_top = qrcode_rect.bottom
        for text, rect in texts:
            if text_bottom:
                rect.top = last_top
            win.surface.blit(text, rect)
            last_top = rect.bottom
        return texts
    

def handler(signum, frame):
    LOGGER.debug("SIGHUP")
    pass

@pibooth.hookimpl
def pibooth_startup(cfg):
    signal.signal(signal.SIGHUP, handler )
    """
    Check the coherence of options.
    """
    LOGGER.info(f"pibooth-qrcode - Hello from {SECTION}")

    for state in ('wait', 'print'):
        if cfg.get(SECTION, '{}_location'.format(state)) not in LOCATIONS:
            raise ValueError("Unknown QR code location on '{}' state '{}'".format(
                             state, cfg.get(SECTION, '{}_location'.format(state))))
        
    if cfg.get(SECTION, 'text_position') not in TEXT_POSITIONS:
            raise ValueError("Unknown text position '{}'".format(cfg.get(SECTION, 'text_position')))


@pibooth.hookimpl
def state_wait_enter(cfg, app, win):
    """
    Display the QR Code on the wait view.
    """
    if hasattr(app, 'previous_qr') and app.previous_picture:
        win_rect = win.get_rect()
        offset = cfg.gettuple(SECTION, 'offset', int, 2)
        location = cfg.get(SECTION, 'wait_location')
        qrcode_rect = get_qrcode_rect(win_rect, app.previous_qr, location, offset)
        win.surface.blit(app.previous_qr, qrcode_rect)
        texts = place_text(cfg, win_rect, qrcode_rect, location, win)
        app.qr_texts = texts
        app.qr_rect = qrcode_rect


@pibooth.hookimpl
def state_wait_do(app, win):
    """
    Redraw the QR Code because it may have been erased by a screen update (
    for instance, if a print is done).
    """
    
    if hasattr(app,"plugin_gallery"):
            if app.plugin_gallery["active"]: 
                #gallery is active. Don't show th QR code
                return

    if hasattr(app, 'previous_qr') and app.previous_picture:
        # Not displayed if no previous capture is deleted
        win.surface.blit(app.previous_qr, app.qr_rect.topleft)
        if hasattr(app, 'qr_texts'):
            for text, rect in app.qr_texts:
                win.surface.blit(text, rect)


@pibooth.hookimpl(trylast=True)
def state_processing_exit(cfg, app):
    """
    Generate the QR Code and store it in the application.
    """
    if qrcode is None:
        raise ModuleNotFoundError("No module named 'qrcode'")
    qr = qrcode.QRCode(version=1,
                       error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=cfg.gettyped("QRCODE", 'size'),
                       border=cfg.gettyped("QRCODE", 'border_size'))

    url_vars = {'picture': app.picture_filename,
                'count': app.count,
                'url': getattr(app, 'previous_picture_url', None) or ''}

    qr.add_data(cfg.get(SECTION, 'prefix_url').format(**url_vars))
    qr.make(fit=True)
    qrcode_fill_color = '#%02x%02x%02x' % cfg.gettyped("QRCODE", 'foreground')
    qrcode_background_color = '#%02x%02x%02x' % cfg.gettyped("QRCODE", 'background')

    image = qr.make_image(fill_color=qrcode_fill_color, back_color=qrcode_background_color)
    app.previous_qr = pygame.image.fromstring(image.tobytes(), image.size, image.mode)


@pibooth.hookimpl
def state_print_enter(cfg, app, win):
    """
    Display the QR Code on the print view.
    """
    win_rect = win.get_rect()
    offset = cfg.gettuple(SECTION, 'offset', int, 2)
    location = cfg.get(SECTION, 'print_location')
    qrcode_rect = get_qrcode_rect(win_rect, app.previous_qr, location, offset)
    
    place_text(cfg, win_rect, qrcode_rect, location, win)
    
    win.surface.blit(app.previous_qr, qrcode_rect.topleft)

@pibooth.hookimpl
def pibooth_cleanup(app):
    """Actions performed at the cleanup of pibooth.

    :param app: application instance
    """
    LOGGER.debug("CLEANUP!!!!")
