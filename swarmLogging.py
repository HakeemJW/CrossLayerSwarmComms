from mininet.node import Controller
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import Station, OVSKernelAP
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
import time
import threading
import os

def log_metrics(sta_list, duration):
    import time

    ap_ip = '10.0.0.254'
    sta1_ip = '10.0.0.1'
    start_time = time.time()
    log_file = open("network_metrics.log", "w")
    log_file.write("Time,Station,Latency(ms),Bandwidth(Mbps),PacketDeliveryRate(%)\n")

    while time.time() - start_time < duration:
        for sta in sta_list:
            # ---- Latency & Packet Delivery ----
            ping_output = sta.cmd(f'ping -c 5 {sta1_ip}')
            latency_lines = [line for line in ping_output.split('\n') if "time=" in line]
            latency_values = [
                float(line.split('time=')[-1].split(' ')[0])
                for line in latency_lines if 'time=' in line
            ]
            avg_latency = round(sum(latency_values) / len(latency_values), 2) if latency_values else -1

            loss_line = [line for line in ping_output.split('\n') if "packet loss" in line]
            if loss_line:
                try:
                    percent_lost = float(loss_line[0].split('%')[0].split()[-1])
                    delivery_rate = round(100 - percent_lost, 2)
                except:
                    delivery_rate = 0
            else:
                delivery_rate = 0

            # ---- Bandwidth (sequential) ----
            bw_output = sta.cmd(f'iperf -c {sta1_ip} -p 5002 -u -b 1G -t 2 -y C')
            print(f"[{sta.name}] iperf output:\n{bw_output.strip()}")

            try:
                lines = bw_output.strip().split('\n')
                last_line = lines[-1] if lines else ''
                fields = last_line.split(',')
                if len(fields) >= 9:
                    bits_per_sec = float(fields[8])  # bits/sec
                    bandwidth = round(bits_per_sec / 1e6, 2)  # Mbps
                else:
                    bandwidth = -1
            except Exception as e:
                print(f"[{sta.name}] Error parsing bandwidth: {e}")
                bandwidth = -1

            # ---- Log ----
            current_time = round(time.time() - start_time, 2)
            log = f"{current_time},{sta.name},{avg_latency},{bandwidth},{delivery_rate}\n"
            print(log.strip())
            log_file.write(log)

            time.sleep(1)  # wait to avoid collisions

        time.sleep(2)  # wait between rounds

    log_file.close()

def topology():
    net = Mininet_wifi(controller=Controller, link=wmediumd, wmediumd_mode=interference, accessPoint=OVSKernelAP)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', position='50,50,0')
    sta2 = net.addStation('sta2', position='10,20,0')
    sta3 = net.addStation('sta3', position='15,25,0')
    sta4 = net.addStation('sta4', position='20,30,0')
    ap1 = net.addAccessPoint('ap1', ssid='swarmnet', mode='g', channel='1', position='50,50,0', range=40)
    c1 = net.addController('c1')

    net.setPropagationModel(model="logDistance", exp=4)
    net.configureWifiNodes()

    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)
    net.addLink(sta3, ap1)
    net.addLink(sta4, ap1)

    # ✅ Set real IP address on AP's wireless interface
    ap1.setIP('10.0.0.254', intf='ap1-wlan1')

    net.plotGraph(max_x=100, max_y=100)

    info("*** Starting mobility\n")
    net.startMobility(time=0)
    net.mobility(sta2, 'start', time=1, position='10,20,0')
    net.mobility(sta2, 'stop', time=20, position='60,60,0')
    net.mobility(sta3, 'start', time=1, position='15,25,0')
    net.mobility(sta3, 'stop', time=20, position='55,65,0')    
    net.mobility(sta4, 'start', time=1, position='20,30,0')
    net.mobility(sta4, 'stop', time=20, position='50,70,0')
    net.stopMobility(time=21)

    info("*** Starting network\n")
    net.build()
    c1.start()
    ap1.start([c1])

    info("*** Starting iperf server on AP\n")
    sta1.cmd('pkill -f iperf')  # kill any existing server
    sta1.cmd('iperf -s -u -p 5002 -B 10.0.0.1 > /tmp/iperf_server.log 2>&1 &')
    time.sleep(2)  # ensure server is up before clients connect

    info("*** Waiting for simulation to complete...\n")
    duration = 25  # total time to log
    thread = threading.Thread(target=log_metrics, args=([sta2, sta3, sta4], duration))
    thread.start()

    thread.join()  # wait for logging to finish
    CLI(net)

    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
