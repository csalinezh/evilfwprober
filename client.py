import asyncio
import time, math

from collections import namedtuple

# Custom sleep example https://stackoverflow.com/questions/37209864/interrupt-all-asyncio-sleep-currently-executing

SIMULTANEOUS_COUNT = 3
RTT_COMPENSATE = 1
EXTRA_WAIT = 2

PROBE_LOWER = 6
PROBE_UPPER = 30
PROBE_TIMEOUT_RESOLUTION = 1

# Use connection pool https://stackoverflow.com/questions/55879847/asyncio-how-to-reuse-a-socket

ProberContext = namedtuple('ProberContext', ['stream', 'timeout'])

class TransportTimeout(Exception):
    """Timeout detected by periodical probe. Probably caused by NAT session invalidation"""
    pass

#async def wait_probe(reader):
#    return await reader.readline()

#class PassiveProber


async def passive_prober(reader,writer,timeout):
    writer.write(b'%d\n' % timeout)
    await writer.drain()
    probe_start_ts = time.monotonic()
    print(f"Request sent. Expecting probe coming back in {timeout} seconds")

    echo_received = None
    probe_task = asyncio.create_task(reader.readline())
    try:
        await asyncio.wait_for(asyncio.shield(probe_task), timeout + RTT_COMPENSATE)
    except asyncio.TimeoutError:
        print (f"{time.monotonic() - probe_start_ts} sec has passed since the request is sent")
        echo_received = False
    else:
        echo_received = True
    
    if not echo_received:
        try:
            await asyncio.wait_for(probe_task, EXTRA_WAIT)
        except asyncio.TimeoutError:
            # probe_task would have been cancelled by asyncio.wait_for()
            print("Response timed out")
            raise TransportTimeout

    try:
        probe_msg = probe_task.result()
    except:
        # The read task might fail unexpectedly. However I forgot how it failed.
        # TODO: Consider how to process error
        raise
    else:
        print(f"Received response {probe_msg.decode().rstrip()}")

async def probe_controller(host, simultaneous_limit):
    range_low = PROBE_LOWER
    range_high = PROBE_UPPER
    task_map = {}

    while True:
        range_low, range_high = await probe_worker(range_low, range_high, host,
            simultaneous_limit, task_map
        )

        if range_high - range_low <= PROBE_TIMEOUT_RESOLUTION:
            return range_low, range_high

async def probe_worker(range_low, range_high, host, simultaneous_limit, task_stream_pair):
    timeout_list = exponential_timeout(range_low, range_high, simultaneous_limit)
    conn_count = len(timeout_list)
    connection_list = [timed_open_connection(*host) for i in range(conn_count)]
    stream_list = await asyncio.gather(*connection_list)

    probe_type = "timeout-probe"
    task_name = []
    for _, curr_writer in stream_list:
        curr_gai = curr_writer.get_extra_info('sockname')
        sport = curr_gai[1]
        task_name.append(f"{probe_type}-{sport}")
    context_list = [ProberContext(s, t) for s,t in zip(stream_list, timeout_list)]
    task_stream_pair.update(zip(task_name, context_list))

    task_list = [asyncio.create_task(
        passive_prober(*stream, tout), name=tname)
        for stream, tout, tname in zip(stream_list, timeout_list, task_name)
    ]

    done = None
    pending = task_list[:]
    new_range_bound_found = False
    while pending and not new_range_bound_found:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for fin_task in done:
            probe_succeed = None
            curr_stream, curr_timeout = task_stream_pair[fin_task.get_name()]
            try:
                print(fin_task.result())
            except TransportTimeout as e:
                probe_succeed = False
                # Corresponding stream should be closed
                failed_writer = curr_stream[1]
                failed_writer.close()
                await failed_writer.wait_closed()
                print(e)
            else:
                probe_succeed = True
            
            if probe_succeed:
                # For debugging
                if curr_timeout < range_low:
                    print(f"ANOMALY REDUCTION: Previous timeout: {range_low} Current timeout: {curr_timeout}")
                range_low = max(range_low, curr_timeout)
            else:
                if curr_timeout > range_high:
                    print(f"ANOMALY INCREASE: Previous timeout: {range_high} Current timeout: {curr_timeout}")
                # Rethink how to process such event

                new_range_bound_found = True
                # FIXME: Consider what to do with pending connections that have higher timeout
                # At least close them unconditionally?
                range_high = min(range_high, curr_timeout)
            print(f"Current range: [{range_low}, {range_high}]")
    
    return range_low, range_high


def trigger_when_half_complete(event, ):
    event.set()

def exponential_timeout(lower, upper, count):
    range_log_l = math.log(lower)
    range_log_h = math.log(upper)
    range_log_delta = (range_log_h - range_log_l) / (count + 1)

    timeout_list = []
    prev_timeout = 0
    for i in range(count):
        # lower * (upper/lower) ^ ( (i+1)/(count+1) )
        curr_timeout = round(math.exp(range_log_l + range_log_delta * (i+1)))
        if curr_timeout - prev_timeout >= PROBE_TIMEOUT_RESOLUTION:
            timeout_list.append(curr_timeout)
            prev_timeout = curr_timeout
        else:
            continue

    return timeout_list

# Inspired by gamma correction curve in digital image processing
# gamma > 1 will cluster near the lower bound, while gamma < 1 will do the opposite.
def gamma_timeout(lower, upper, gamma, count):
    range_norm_l = lower/upper
    range_norm_h = 1 # upper/upper
    range_norm_delta = (range_norm_h - range_norm_l) / (count + 1)

    timeout_list = []
    prev_timeout = 0
    for i in range(count):
        curr_timeout = round(upper * ((range_norm_l + range_norm_delta * (i+1)) ** gamma))
        if curr_timeout - prev_timeout >= PROBE_TIMEOUT_RESOLUTION:
            timeout_list.append(curr_timeout)
            prev_timeout = curr_timeout
        else:
            continue

    return timeout_list

def timed_open_connection(host=None, port=None, timeout=7, **kwargs):
    # Socket might stay in SYN_SENT for several minutes because of blocked TCP SYN
    # Wait for 7 seconds by default.
    return asyncio.wait_for(asyncio.open_connection(host, port, **kwargs), timeout)

async def main():
    timeout_bound = await probe_controller(('127.0.0.1', 7545), SIMULTANEOUS_COUNT)
    print(timeout_bound)


'''
TEST_TIMEOUT = 5
async def main():
    reader,writer = await asyncio.open_connection(        
        '127.0.0.1', 7545
    )

    await passive_prober(reader,writer,TEST_TIMEOUT)
'''
if __name__ == '__main__':
    asyncio.run(main(), debug=True)
