"""Send RC channels to an MSP receiver."""

import struct
import time
from beta_client.entities import RcChannels

from beta_client.transport import Transport

MSP_V1_REQUEST = b'$M<'
MSP_SET_RAW_RC = 200
MSP_BOARD_INFO = 4
MSP_BOARD_IDENTIFIER_LENGTH = 4
MSP_BOARD_INFO_TIMEOUT_S = 1.0
MSP_BOARD_INFO_MAX_FRAME = 261
RC_CHANNEL_COUNT = 8
RC_CHANNEL_MAX = 0xFFFF


def build_rc_message(channels: RcChannels) -> bytes:
    """Build an MSP v1 RC frame from eight unsigned 16-bit channel values."""
    payload = struct.pack('<8H', *channels.values)
    body = bytes((len(payload), MSP_SET_RAW_RC)) + payload
    checksum = 0
    for byte in body:
        checksum ^= byte
    return MSP_V1_REQUEST + body + bytes((checksum,))


def send_rc(transport: Transport, channels: RcChannels) -> None:
    """Send an RC frame using an open transport."""
    transport.send(build_rc_message(channels))


def read_board_identifier(transport, *, timeout_s: float = MSP_BOARD_INFO_TIMEOUT_S) -> str:
    """Request and validate the four-byte MSP v1 board identifier."""
    if timeout_s <= 0:
        raise ValueError('MSP board-info timeout must be positive')
    request = bytes((0, MSP_BOARD_INFO, MSP_BOARD_INFO))
    transport.send(MSP_V1_REQUEST + request)
    deadline = time.monotonic() + timeout_s
    buffer = bytearray()
    while time.monotonic() < deadline:
        try:
            chunk = transport.receive(MSP_BOARD_INFO_MAX_FRAME)
        except TimeoutError:
            continue
        if not chunk:
            raise ConnectionError('MSP connection closed during board-info request')
        buffer.extend(chunk)
        if len(buffer) > MSP_BOARD_INFO_MAX_FRAME * 2:
            raise ValueError('MSP board-info response exceeded its bound')
        while len(buffer) >= 3:
            start = buffer.find(b'$M')
            if start < 0:
                buffer.clear()
                break
            if start:
                del buffer[:start]
            if len(buffer) < 6:
                break
            if buffer[2] not in (ord('>'), ord('!')):
                del buffer[0]
                continue
            length = buffer[3]
            frame_length = 6 + length
            if len(buffer) < frame_length:
                break
            frame = bytes(buffer[:frame_length])
            del buffer[:frame_length]
            if frame[4] != MSP_BOARD_INFO:
                continue
            if frame[2] == ord('!'):
                raise ValueError('MSP board-info request was rejected')
            checksum = 0
            for byte in frame[3:-1]:
                checksum ^= byte
            if checksum != frame[-1]:
                raise ValueError('Invalid MSP board-info checksum')
            if length < MSP_BOARD_IDENTIFIER_LENGTH:
                raise ValueError('Short MSP board-info response')
            try:
                return frame[5:5 + MSP_BOARD_IDENTIFIER_LENGTH].decode('ascii')
            except UnicodeDecodeError as error:
                raise ValueError('Invalid MSP board identifier') from error
    raise TimeoutError('MSP board-info response timed out')
