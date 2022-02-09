# evilfwprober
Examine how those evil middleboxes mess with your connections.

## Features
- [x] Measure the session timeout of established TCP connections
- [ ] Measure the session timeout for UDP
- [ ] Test whether TCP Simultaneous Open works

## Usage
This project requires Python 3.7+

For server side, modify the listen address in `server.py` and execute it with Python.

At client side, modify `client.py` to use server address as arguments when calling `probe_controller()`. The constants `PROBE_LOWER` and `PROBE_UPPER` should be modified to set the search range (in seconds).

After client-side configuration, start the probe by executing `client.py` with Python. The program will run until it narrows the range to `PROBE_TIMEOUT_RESOLUTION` seconds. Multiple concurrent probe connections can be used to speed up the process by setting `SIMULTANEOUS_COUNT` to an integer greater than 1.

## Emulate a connection loss caused by session invalidation in middleboxes
When a NAT or session mapping expires in middleboxes, the client behind it won't be able to hear from the server using the previous endpoint (public IP and port pair). This can be emulated with firewall rules in `iptables` that drop inbound packets. Users can manually set or remove such rules in their test environment after TCP connection is established.
```shell
# Set
iptables -t filter -I INPUT --source <server ip> -m tcp -p tcp --sport <server listen port> -j DROP
# Revert
iptables -t filter -D INPUT --source <server ip> -m tcp -p tcp --sport <server listen port> -j DROP
```
