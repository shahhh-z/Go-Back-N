import time
from queue import *
from logging import *
from threading import Thread

class GBN_sender:
    def __init__(self, input_file, window_size, packet_len, nth_packet, send_queue, ack_queue, timeout_interval, logger):
        self.input_file = input_file
        self.window_size = window_size
        self.packet_len = packet_len
        self.nth_packet = nth_packet
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.timeout_interval = timeout_interval
        self.logger = logger
        self.base = 0
        self.packets = self.prepare_packets()
        self.acks_list = [False] * len(self.packets)
        self.packet_timers = [0] * len(self.packets)
        self.dropped_list = []
        self.num_sent = 0
        self.logger.info(f"{len(self.packets)} packets created, Window size: {self.window_size}, Packet length: {self.packet_len}, Nth packed to be dropped: {self.nth_packet}, Timeout interval: {self.timeout_interval}")
    

    def prepare_packets(self):
        file = open(f"{self.input_file}", "r")
        words = file.read()
        binary_rep = "".join(format(ord(x),'08b') for x in words)
        data_bits = self.packet_len - 16
        packets = []
        seq_num = 0

        for i in range(0, len(binary_rep), data_bits):
            data = binary_rep[i:i + data_bits]
            if len(data) < data_bits:
                data = data + ('0' * (data_bits - len(data)))
            seq_padded = format(seq_num, '016b')
            packet = data + seq_padded
            packets.append(packet)
            seq_num += 1
        
        return packets
    

    def send_packets(self):
        for packet_num in range(self.base, min(self.base + self.window_size, len(self.packets))):
            seq_num = int(self.packets[packet_num][-16:], 2)
            self.num_sent += 1
            self.logger.info(f"Sender: sending packet {seq_num}")
            if self.num_sent % self.nth_packet == 0:
                self.dropped_list.append(seq_num)
                self.logger.info(f"Sender: packet {seq_num} dropped")
                self.packet_timers[packet_num] = time.time()
            else:
                self.send_queue.put(self.packets[packet_num])
                self.packet_timers[packet_num] = time.time()
    

    def send_next_packet(self):
        self.base += 1
        packet_num = self.base + self.window_size - 1
        if (packet_num < len(self.packets)):
            self.num_sent += 1
            seq_num = int(self.packets[packet_num][-16:], 2)
            self.logger.info(f"Sender: sending packet {seq_num}")
            if self.num_sent % self.nth_packet == 0:
                self.dropped_list.append(seq_num)
                self.logger.info(f"Sender: packet {seq_num} dropped")
                self.packet_timers[packet_num] = time.time()
            else:
                self.send_queue.put(self.packets[packet_num])
                self.packet_timers[packet_num] = time.time()
    
    
    def check_timers(self):
        for packet_num in range(self.base, min(self.base + self.window_size, len(self.packets))):
            if self.packet_timers[packet_num] != 0:
                time_elapsed = time.time() - self.packet_timers[packet_num]
                if time_elapsed >= self.timeout_interval:
                    seq_num = int(self.packets[packet_num][-16:], 2)
                    self.logger.info(f"Sender: packet {seq_num} timed out")
                    self.packet_timers[packet_num] = 0
                    return True
    
        return False
    

    def receive_acks(self):
        while True:
            try:
                ack = self.ack_queue.get(timeout=0.01)
                self.packet_timers[ack - 1] = 0
                if (self.acks_list[ack] == False):
                    self.acks_list[ack] = True
                    self.logger.info(f"Sender: ack {ack} received")
                    self.send_next_packet()
                else:
                    self.logger.info(f"Sender: ack {ack} received, Ignoring")
            except Empty:
                continue
            except Exception as e:
                print(e)
            """
            I needed to slow this function down a bit since it was shifting the
            window before some previous packets were resent (after a timeout).
            """
            time.sleep(0.2)
    

    def run(self):
        self.send_packets()
        Thread(target=self.receive_acks, daemon=True).start()
        while (self.base < len(self.packets)):
            if (self.check_timers() == True):
                self.send_packets()
        self.send_queue.put(None)
        self.logger.info("Sender: All packets have been sent and acknowledgments processed.")



class GBN_receiver:
    def __init__(self, output_file, send_queue, ack_queue, logger):
        self.output_file = output_file
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.logger = logger
        self.packet_list = []
        self.expected_seq_num = 0
    

    def process_packet(self, packet):
        seq_num = int(packet[-16:], 2)
        if (seq_num == self.expected_seq_num):
            self.packet_list.append(packet)
            self.ack_queue.put(seq_num)
            self.expected_seq_num += 1
            self.logger.info(f"Receiver: packet {seq_num} received")
            return True
        
        else:
            self.ack_queue.put(self.expected_seq_num - 1)
            self.logger.info(f"Receiver: packet {seq_num} received out of order")
            return False
    

    def write_to_file(self):
        data = []
        for packet_num in range(0, len(self.packet_list)):
            packet = self.packet_list[packet_num][:-16]
            for i in range(0, len(packet), 8):
                byte = packet[i:i+8]
                if byte != "00000000":
                    char = chr(int(byte, 2))
                    data.append(char)
        message = "".join(data)

        try:
            output_file = open(self.output_file, "w")
            output_file.write(message)
            output_file.close()
        except Exception as e:
            print(e)
    

    def run(self):
        while True:
            try:
                packet = self.send_queue.get(timeout=0.01)
                if packet == None:
                    break
                else:
                    self.process_packet(packet)
            except Empty:
                continue
            except Exception as e:
                print(e)
        self.write_to_file()