from go_back_n import GBN_sender, GBN_receiver
import threading, queue, logging
from time import time

log_file = 'simulation.log'
in_file = 'input_test.txt'
out_file = 'output_test.txt'
# with open(in_file, 'w') as f: f.write("Hello World")

window_size = 6
packet_len = 80
nth_packet = 20
timeout_interval = 3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, 'w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(file_handler)

send_queue, ack_queue = queue.Queue(), queue.Queue()
sender = GBN_sender(input_file = in_file, window_size = window_size, packet_len = packet_len, nth_packet = nth_packet, send_queue = send_queue, ack_queue = ack_queue, timeout_interval = timeout_interval, logger = logger)
receiver = GBN_receiver(output_file = out_file, send_queue = send_queue, ack_queue = ack_queue, logger = logger)

sender_thread = threading.Thread(target=sender.run)
start = time()
sender_thread.start()
receiver.run() 
sender_thread.join() 

with open(in_file, 'r') as f1, open(out_file, 'r') as f2: sent, received = f1.read(), f2.read()
if sent == received: print("Data transmitted successfully!")
end = time()
print(f"{end-start} seconds elapsed")