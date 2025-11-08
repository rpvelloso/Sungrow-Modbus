from pymodbus.client import (
    ModbusTcpClient,
    AsyncModbusTcpClient,
)
from pymodbus.pdu.diag_message import RestartCommunicationsOptionRequest
from Cryptodome.Cipher import AES
from pymodbus.logging import Log
from datetime import date
import asyncio

PRIV_KEY = b'Grow#0*2Sun68CbE'
NO_CRYPTO1 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
NO_CRYPTO2 = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
GET_KEY = b'\x68\x68\x00\x00\x00\x06\xf7\x04\x0a\xe7\x00\x08'
HEADER = bytes([0x68, 0x68])

# class SungrowModbusTcpClient(ModbusTcpClient):
#     def __init__(self, priv_key=PRIV_KEY, **kwargs):
#         ModbusTcpClient.__init__(self, **kwargs)
#         self._fifo = bytes()
#         self._priv_key = priv_key
#         self._key = None
#         self._orig_recv = self.recv
#         self._orig_send = self.send
#         self._key_date = date.today()

#     def _setup(self):
#            self._key = bytes(a ^ b for (a, b) in zip(self._pub_key, self._priv_key))
#            self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
#            self._key_date = date.today()
#            self.send = self._send_cipher
#            self.recv = self._recv_decipher
#            self._fifo = bytes()

#     def _restore(self):
#            self._key = None
#            self._aes_ecb = None
#            self.send = self._orig_send
#            self.recv = self._orig_recv
#            self._fifo = bytes()

#     def _getkey(self):
#         if (self._key is None) or (self._key_date != date.today()):
#            self._restore()
#            self.send(GET_KEY)
#            self._key_packet = self.recv(25)
#            self._pub_key = self._key_packet[9:]
#            if (len(self._pub_key) == 16) and (self._pub_key != NO_CRYPTO1) and (self._pub_key != NO_CRYPTO2):
#               self._setup()
#            else:
#               self._key = b'no encryption'
#               self._key_date = date.today()

#     def connect(self):
#         self.close()
#         result = ModbusTcpClient.connect(self)
#         if not result:
#             self._restore()
#         else:
#             self._getkey()
#             if self._key is not None:
#                # We now have the encryption key stored and a second
#                # connect will likely succeed.
#                self.close()
#                result = ModbusTcpClient.connect(self)
#         return result

#     def close(self):
#        ModbusTcpClient.close(self)
#        self._fifo = bytes()

#     def _send_cipher(self, request):
#         self._fifo = bytes()
#         length = len(request)
#         padding = 16 - (length % 16)
#         self._transactionID = request[:2]
#         request = HEADER + bytes(request[2:]) + bytes([0xff for i in range(0, padding)])
#         crypto_header = bytes([1, 0, length, padding])
#         encrypted_request = crypto_header + self._aes_ecb.encrypt(request)
#         return ModbusTcpClient.send(self, encrypted_request) - len(crypto_header) - padding

#     def _recv_decipher(self, size):
#         if len(self._fifo) == 0:
#             header = ModbusTcpClient.recv(self, 4)
#             if header and len(header) == 4:
#                packet_len = int(header[2])
#                padding = int(header[3])
#                length = packet_len + padding
#                encrypted_packet = ModbusTcpClient.recv(self, length)
#                if encrypted_packet and len(encrypted_packet) == length:
#                   packet = self._aes_ecb.decrypt(encrypted_packet)
#                   packet = self._transactionID + packet[2:]
#                   self._fifo = self._fifo + packet[:packet_len]

#         if size is None:
#            recv_size = 1
#         else:
#            recv_size = size

#         recv_size = min(recv_size, len(self._fifo))
#         result = self._fifo[:recv_size]
#         self._fifo = self._fifo[recv_size:]
#         return result


class SungrowModbusTcpClient(ModbusTcpClient):
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        self._wrapper = SungrowModbusTCPWrapper(priv_key=priv_key, **kwargs)
        # Insert our own trace_packet function.
        kwargs['trace_packet'] = self._wrapper.trace_packet
        super().__init__(**kwargs)
        self._connect_underway = False

    def connect(self) -> bool:
        if self._connect_underway:
            return True
        self._connect_underway = True
        try:
            print("Connecting")
            result = super().connect()
            response = None
            if result:
                print("Connected, sending handshake.")
                self._wrapper._state = 'HANDSHAKE'
                # This sends a synchronous request to trigger sending the GET_KEY packet
                # self.transaction.pdu_send(RestartCommunicationsOptionRequest())
                self.execute(no_response_expected=True, request=RestartCommunicationsOptionRequest())
                if self._wrapper.pub_key is not None:
                    response = self._wrapper.pub_key

            return result and response is not None
        finally:
            self._connect_underway = False

    def close(self):
       super().close()
       self._wrapper.reset()


class AsyncSungrowModbusTcpClient(AsyncModbusTcpClient):
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        self._wrapper = SungrowModbusTCPWrapper(priv_key=priv_key, **kwargs)
        # Insert our own trace_packet function.
        kwargs['trace_packet'] = self._wrapper.trace_packet
        super().__init__(**kwargs)

    async def connect(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** connect")
        result = await super().connect()
        response = None
        if result:
            self._wrapper._state = 'HANDSHAKE'
            async with self.ctx._lock:
                response_future = asyncio.Future()
                self._wrapper.set_response_future(response_future)
                # This will trigger the sending of the GET_KEY packet
                self.execute(no_response_expected=True, request=RestartCommunicationsOptionRequest())
                response = await asyncio.wait_for(
                    response_future, timeout=self.comm_params.timeout_connect
                )
        return result and response is not None

    def close(self):
       Log.debug("*** AsyncSungrowModbusTcpClient *** close")
       super().close()
       self._wrapper.reset()


class SungrowModbusTCPWrapper():
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        # Save the caller's trace_packet function, if present.
        self._caller_trace_packet: callable[[bool, bytes], bytes] | None = kwargs.pop('trace_packet', None)
        self._priv_key = priv_key
        self.reset()
        self._response_future: asyncio.Future | None = None
        self.pub_key: bytes | None = None

    def reset(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** reset")
        self._state = 'INIT'
        self._fifo = bytes()
        self._key = None

    def _setup(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** setup pub_key {}", self.pub_key)
        self._key = bytes(a ^ b for (a, b) in zip(self.pub_key, self._priv_key))
        self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
        self._state = 'CRYPTO'

    def _send_cypher(self, request: bytes) -> bytes:
        length = len(request)
        padding = 16 - (length % 16)
        self._transactionID = request[:2]
        request = HEADER + bytes(request[2:]) + bytes([0xff for i in range(0, padding)])
        crypto_header = bytes([1, 0, length, padding])
        return crypto_header + self._aes_ecb.encrypt(request)

    def _recv_handshake(self, data: bytes) -> bytes:
        self._fifo = self._fifo + data
        if len(self._fifo) >= 25:
            self.pub_key = self._fifo[9:25]
            if (self.pub_key != NO_CRYPTO1) and (self.pub_key != NO_CRYPTO2):
                # If the buffer contained the pubkey, strip it off
                self._fifo = self._fifo[25:]
                self._setup()
            else:
                self._state = 'NO_CRYPTO'
                self.pub_key = None
            if self._response_future is not None:
                self._response_future.set_result(self.pub_key)
        return self._fifo

    def _recv_cypher(self, data: bytes) -> bytes:
        self._fifo = self._fifo + data
        output = bytes()
        while len(self._fifo) >= 4:
            packet_len = int(self._fifo[2])
            padding = int(self._fifo[3])
            length = packet_len + padding + 4
            if len(self._fifo) >= length:
                encrypted_packet = self._fifo[4:length]
                self._fifo = self._fifo[length:]
                packet = self._aes_ecb.decrypt(encrypted_packet)
                packet = self._transactionID + packet[2:]
                output += packet
            else:
                break
        return output

    def set_response_future(self, future: asyncio.Future):
        self._response_future = future

    def trace_packet(self, sending: bool, data: bytes) -> bytes:
        """
            This function is called when sending or receiving bytes on the network.
            It handles encryption/decryption as needed, and calls the original
            trace_packet function provided by the caller, if any.
        """
        print(f"trace_packet: state={self._state}, sending={sending}, data={data.hex()}")
        if sending:
            if self._caller_trace_packet:
                data = self._caller_trace_packet(sending, data)
            if self._state == 'CRYPTO':
                data = self._send_cypher(data)
            elif self._state == 'HANDSHAKE':
                # Overwrite the data to be sent with the GET_KEY packet
                data = GET_KEY
        else:
            # Receiving
            if self._state == 'CRYPTO':
                data = self._recv_cypher(data)
            elif self._state == 'HANDSHAKE':
                data = self._recv_handshake(data)
            if self._caller_trace_packet:
                self._caller_trace_packet(sending, data)
        print(f"Sending data: {data.hex()}")
        return data
