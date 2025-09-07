from pymodbus.client import AsyncModbusTcpClient
from pymodbus.logging import Log
from Cryptodome.Cipher import AES
import asyncio

PRIV_KEY = b'Grow#0*2Sun68CbE'
NO_CRYPTO1 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
NO_CRYPTO2 = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
GET_KEY = b'\x68\x68\x00\x00\x00\x06\xf7\x04\x0a\xe7\x00\x08'
HEADER = bytes([0x68, 0x68])

def raise_():
    raise Exception("Invalid state")

class AsyncSungrowModbusTcpClient(AsyncModbusTcpClient):
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        AsyncModbusTcpClient.__init__(self, **kwargs)
        Log.debug("*** AsyncSungrowModbusTcpClient *** init priv_key {}", priv_key)
        self._orig_callback_data = self.ctx.callback_data
        self._orig_low_level_send = self.ctx.low_level_send
        self._priv_key = priv_key
        self._reset()

    def _reset(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** reset")
        self._state = 'INIT'
        self.ctx.callback_data = self._callback_data_decipher
        self.ctx.low_level_send = self._orig_low_level_send
        self._fifo = bytes()
        self._key = None

    def _setup(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** setup pub_key {}", self._pub_key)
        self._key = bytes(a ^ b for (a, b) in zip(self._pub_key, self._priv_key))
        self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
        self._state = 'CRYPTO'
        self.ctx.low_level_send = self._low_level_send_cipher

    async def connect(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** connect")
        result = await AsyncModbusTcpClient.connect(self)
        response = None
        if result:
            self._state = 'HANDSHAKE'
            async with self.ctx._lock:
                self.response_future = asyncio.Future()
                self._orig_low_level_send(GET_KEY)
                response = await asyncio.wait_for(
                    self.response_future, timeout=self.comm_params.timeout_connect
                )
        return result and response is not None

    def close(self):
       Log.debug("*** AsyncSungrowModbusTcpClient *** close")
       AsyncModbusTcpClient.close(self)
       self._reset()

    def _low_level_send_cipher(self, request, addr: tuple | None = None):
        Log.debug("*** AsyncSungrowModbusTcpClient *** cypher {}", len(request))
        length = len(request)
        padding = 16 - (length % 16)
        self._transactionID = request[:2]
        request = HEADER + bytes(request[2:]) + bytes([0xff for i in range(0, padding)])
        crypto_header = bytes([1, 0, length, padding])
        encrypted_request = crypto_header + self._aes_ecb.encrypt(request)
        self._orig_low_level_send(encrypted_request, addr)

    def handshake_state(self, data: bytes, addr: tuple | None = None) -> int:
        self._fifo = self._fifo + data
        if len(self._fifo) >= 25:
            self._pub_key = self._fifo[9:25]
            self._fifo = self._fifo[25:]
            if (self._pub_key != NO_CRYPTO1) and (self._pub_key != NO_CRYPTO2):
                self._setup()
            else:
                self._state = 'NO_CRYPTO'
            self.response_future.set_result(self._pub_key)
        return len(data)
        
    def crypto_state(self, data: bytes, addr: tuple | None = None) -> int:
        self._fifo = self._fifo + data
        if len(self._fifo) >= 4:
            packet_len = int(self._fifo[2])
            padding = int(self._fifo[3])
            length = packet_len + padding + 4
            if len(self._fifo) >= length:
                encrypted_packet = self._fifo[4:length]
                self._fifo = self._fifo[length:]
                packet = self._aes_ecb.decrypt(encrypted_packet)
                packet = self._transactionID + packet[2:]
                self._orig_callback_data(packet, addr)
        return len(data)
    
    def no_crypto_state(self, data: bytes, addr: tuple | None = None) -> int:
        return self._orig_callback_data(data, addr)
    
    states = {
        'INIT': no_crypto_state,
        'HANDSHAKE': handshake_state,
        'CRYPTO': crypto_state,
        'NO_CRYPTO': no_crypto_state,
    }
    
    def _callback_data_decipher(self, data: bytes, addr: tuple | None = None) -> int:
        Log.debug("*** AsyncSungrowModbusTcpClient *** {} decypher {}", self._state, len(data))
        return AsyncSungrowModbusTcpClient.states[self._state](self, data, addr)
