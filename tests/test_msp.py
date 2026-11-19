import unittest
from unittest.mock import Mock, patch

from beta_client.entities import RcChannels
from beta_client.msp import build_rc_message, read_board_identifier, send_rc
from beta_client.transport import SerialTransport, TcpTransport


class MspTests(unittest.TestCase):
    @staticmethod
    def board_frame(identifier=b'SITL'):
        payload = identifier + b'\x00\x00'
        body = bytes((len(payload), 4)) + payload
        checksum = 0
        for byte in body:
            checksum ^= byte
        return b'$M>' + body + bytes((checksum,))

    def test_board_identifier_accepts_fragmented_reply(self):
        transport = Mock()
        frame = self.board_frame()
        transport.receive.side_effect = [frame[:3], frame[3:]]
        self.assertEqual(read_board_identifier(transport), 'SITL')
        transport.send.assert_called_once_with(b'$M<\x00\x04\x04')

    def test_board_identifier_can_be_another_target(self):
        transport = Mock()
        transport.receive.return_value = self.board_frame(b'ABCD')
        self.assertEqual(read_board_identifier(transport), 'ABCD')

    def test_board_identifier_rejects_bad_frames(self):
        valid = self.board_frame()
        short = b'$M>\x02\x04XX\x06'
        for frame in (valid[:-1] + bytes((valid[-1] ^ 1,)), short):
            transport = Mock()
            transport.receive.return_value = frame
            with self.subTest(frame=frame), self.assertRaises((ValueError, TimeoutError)):
                read_board_identifier(transport, timeout_s=0.01)

    def test_board_identifier_times_out(self):
        transport = Mock()
        transport.receive.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            read_board_identifier(transport, timeout_s=0.01)

    def test_frame(self):
        self.assertEqual(build_rc_message(RcChannels((1000,) * 8)), b'$M<\x10\xc8' + b'\xe8\x03' * 8 + b'\xd8')

    def test_invalid_channels(self):
        transport = Mock()
        for channels in ([1000] * 7, [1000] * 7 + [-1], [1000] * 7 + [65536]):
            with self.subTest(channels=channels), self.assertRaises(ValueError):
                send_rc(transport, RcChannels(channels))
        transport.send.assert_not_called()

    @patch('beta_client.transport.socket.create_connection')
    def test_tcp(self, connect):
        with TcpTransport('localhost', 5761) as transport:
            send_rc(transport, RcChannels((1000,) * 8))
        connect.return_value.sendall.assert_called_once_with(build_rc_message(RcChannels((1000,) * 8)))
        connect.return_value.close.assert_called_once()

    @patch('beta_client.transport.serial.Serial')
    def test_serial_partial_writes_and_close(self, serial):
        serial.return_value.write_timeout = 0.02
        serial.return_value.write.side_effect = [1, 2]
        with SerialTransport('/dev/test', 115200) as transport:
            transport.send(b'abc')
        self.assertEqual(bytes(serial.return_value.write.call_args_list[1].args[0]), b'bc')
        serial.return_value.close.assert_called_once()

    @patch('beta_client.transport.serial.Serial')
    def test_serial_no_progress(self, serial):
        serial.return_value.write_timeout = 0.02
        serial.return_value.write.return_value = 0
        with SerialTransport('/dev/test', 115200) as transport, self.assertRaises(OSError):
            transport.send(b'a')
        serial.return_value.close.assert_called_once()

    def test_send_error_propagates(self):
        transport = Mock()
        transport.send.side_effect = OSError('disconnected')
        with self.assertRaises(OSError):
            send_rc(transport, RcChannels((1000,) * 8))


if __name__ == '__main__':
    unittest.main()
