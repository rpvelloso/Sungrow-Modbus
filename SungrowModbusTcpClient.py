from pymodbus.client.sync import ModbusTcpClient
from Crypto.Cipher import AES

priv_key = b'Grow#0*2Sun68CbE'
NO_CRYPTO1 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
NO_CRYPTO2 = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
GET_KEY = b'\x68\x68\x00\x00\x00\x06\xf7\x04\x0a\xe7\x00\x08'
HEADER = bytes([0x68, 0x68])

class SungrowModbusTcpClient(ModbusTcpClient):
    def __init__(self, **kwargs):
        ModbusTcpClient.__init__(self, **kwargs)
        self.fifo = bytes()
        self.key = None

    def _getkey(self):
        self._send(GET_KEY)
        self.key_packet = self._recv(25)
        self.pub_key = self.key_packet[9:]
        if (self.pub_key != NO_CRYPTO1) and (self.pub_key != NO_CRYPTO2):
           self.key = bytes(a ^ b for (a, b) in zip(self.pub_key, priv_key))
           self.decipher = AES.new(self.key, AES.MODE_ECB)
           self._send = self._send_cipher
           self._recv = self._recv_decipher

    def connect(self):
        result = ModbusTcpClient.connect(self)
        if result and not self.key:
           self._getkey()
        return result

    def close(self):
        ModbusTcpClient.close(self)
        self.key = None

    def _send_cipher(self, request):
        length = len(request)
        padding = 16 - (length % 16)
        request = HEADER + bytes(request[2:]) + bytes([0xff for i in range(0, padding)])
        encrypted_request = bytes([1, 0, length, padding]) + self.decipher.encrypt(request)
        return ModbusTcpClient._send(self, encrypted_request)

    def _recv_decipher(self, size):
        if len(self.fifo) < size:
            header = ModbusTcpClient._recv(self, 4)
            if header and len(header) == 4:
               length = int(header[2]) + int(header[3])
               encrypted_packet = ModbusTcpClient._recv(self, length)
               if encrypted_packet and len(encrypted_packet) == length:
                  packet = self.decipher.decrypt(encrypted_packet)
                  self.fifo = self.fifo + packet[:length - header[3]]

        size = min(size, len(self.fifo))
        result = self.fifo[:size]
        self.fifo = self.fifo[size:]
        return result
