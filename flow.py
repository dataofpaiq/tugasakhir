from enum import Enum
from typing import Any
from decimal import Decimal
import math

from . import constants
from .features.context import packet_flow_key
from .features.context.packet_direction import PacketDirection
from .features.flag_count import FlagCount
from .features.flow_bytes import FlowBytes
from .features.packet_count import PacketCount
from .features.packet_length import PacketLength
from .features.packet_time import PacketTime
from .utils import get_statistics


def _to_float_safe(x, default=0.0):
    """Convert x to float safely. Handles Decimal, None, or other numeric types."""
    try:
        if x is None:
            return float(default)
        if isinstance(x, Decimal):
            return float(x)
        return float(x)
    except Exception:
        return float(default)


class Flow:
    """This class summarizes the values of the features of the network flows"""

    def __init__(self, packet: Any, direction: Enum):
        """This method initializes an object from the Flow class.

        Args:
            packet (Any): A packet from the network.
            direction (Enum): The direction the packet is going ove the wire.
        """
        self.protocol = packet.payload.proto if hasattr(packet, "payload") else None

        try:
            (
                self.dest_ip,
                self.src_ip,
                self.src_port,
                self.dest_port,
            ) = packet_flow_key.get_packet_flow_key(packet, direction)

            # Initialize source and destination MAC addresses
            self.src_mac = packet.src if hasattr(packet, "src") else None
            self.dest_mac = packet.dst if hasattr(packet, "dst") else None

            # Inisialisasi tambahan untuk ICMP
            self.icmp_type = None
            self.icmp_code = None
            if packet.haslayer("ICMP"):
                self.icmp_type = packet["ICMP"].type
                self.icmp_code = packet["ICMP"].code

        except Exception as e:
            print(f"Error creating flow key: {e}")
            raise ValueError(f"Cannot create flow from packet: {packet.summary()}")

        self.packets = []
        self.flow_interarrival_time = []
        self.latest_timestamp = 0.0
        self.start_timestamp = 0.0
        self.init_window_size = {
            PacketDirection.FORWARD: 0,
            PacketDirection.REVERSE: 0,
        }

        self.start_active = 0.0
        self.last_active = 0.0
        self.active = []
        self.idle = []

        self.forward_bulk_last_timestamp = 0.0
        self.forward_bulk_start_tmp = 0.0
        self.forward_bulk_count = 0
        self.forward_bulk_count_tmp = 0
        self.forward_bulk_duration = 0.0
        self.forward_bulk_packet_count = 0
        self.forward_bulk_size = 0
        self.forward_bulk_size_tmp = 0
        self.backward_bulk_last_timestamp = 0.0
        self.backward_bulk_start_tmp = 0.0
        self.backward_bulk_count = 0
        self.backward_bulk_count_tmp = 0
        self.backward_bulk_duration = 0.0
        self.backward_bulk_packet_count = 0
        self.backward_bulk_size = 0
        self.backward_bulk_size_tmp = 0

    def get_data(self) -> dict:
        """This method obtains the values of the features extracted from each flow.

        Note:
            Only some of the network data plays well together in this list.
            Time-to-live values, window values, and flags cause the data to
            separate out too much.

        Returns:
           dict: returns a dict of values to be outputted into a csv file.
        """
        flow_bytes = FlowBytes(self)
        flag_count = FlagCount(self)
        packet_count = PacketCount(self)
        packet_length = PacketLength(self)
        packet_time = PacketTime(self)
        flow_iat = get_statistics(self.flow_interarrival_time)
        forward_iat = get_statistics(packet_time.get_packet_iat(PacketDirection.FORWARD))
        backward_iat = get_statistics(packet_time.get_packet_iat(PacketDirection.REVERSE))
        active_stat = get_statistics(self.active)
        idle_stat = get_statistics(self.idle)

        # Make sure numeric outputs are floats to avoid Decimal*float issues
        def _g(k, default=0.0):
            return _to_float_safe(k, default)

        data = {
            # Basic IP information
            "src_ip": self.src_ip,
            "dst_ip": self.dest_ip,
            "src_mac": self.src_mac,
            "dst_mac": self.dest_mac,
            "src_port": self.src_port,
            "dst_port": self.dest_port,
            "protocol": self.protocol,
            # Basic information from packet times
            "timestamp": packet_time.get_time_stamp(),
            "flow_duration": _g(packet_time.get_duration()),
            "flow_byts_s": _g(flow_bytes.get_rate()),
            "flow_pkts_s": _g(packet_count.get_rate()),
            "fwd_pkts_s": _g(packet_count.get_rate(PacketDirection.FORWARD)),
            "bwd_pkts_s": _g(packet_count.get_rate(PacketDirection.REVERSE)),
            # Count total packets by direction
            "tot_fwd_pkts": _g(packet_count.get_total(PacketDirection.FORWARD)),
            "tot_bwd_pkts": _g(packet_count.get_total(PacketDirection.REVERSE)),
            # Statistical info obtained from Packet lengths
            "totlen_fwd_pkts": _g(packet_length.get_total(PacketDirection.FORWARD)),
            "totlen_bwd_pkts": _g(packet_length.get_total(PacketDirection.REVERSE)),
            "fwd_pkt_len_max": _g(packet_length.get_max(PacketDirection.FORWARD)),
            "fwd_pkt_len_min": _g(packet_length.get_min(PacketDirection.FORWARD)),
            "fwd_pkt_len_mean": _g(packet_length.get_mean(PacketDirection.FORWARD)),
            "fwd_pkt_len_std": _g(packet_length.get_std(PacketDirection.FORWARD)),
            "bwd_pkt_len_max": _g(packet_length.get_max(PacketDirection.REVERSE)),
            "bwd_pkt_len_min": _g(packet_length.get_min(PacketDirection.REVERSE)),
            "bwd_pkt_len_mean": _g(packet_length.get_mean(PacketDirection.REVERSE)),
            "bwd_pkt_len_std": _g(packet_length.get_std(PacketDirection.REVERSE)),
            "pkt_len_max": _g(packet_length.get_max()),
            "pkt_len_min": _g(packet_length.get_min()),
            "pkt_len_mean": _g(packet_length.get_mean()),
            "pkt_len_std": _g(packet_length.get_std()),
            "pkt_len_var": _g(packet_length.get_var()),
            "fwd_header_len": _g(flow_bytes.get_forward_header_bytes()),
            "bwd_header_len": _g(flow_bytes.get_reverse_header_bytes()),
            "fwd_seg_size_min": _g(flow_bytes.get_min_forward_header_bytes()),
            "fwd_act_data_pkts": packet_count.has_payload(PacketDirection.FORWARD),
            # Flows Interarrival Time
            "flow_iat_mean": _g(flow_iat.get("mean", 0.0)),
            "flow_iat_max": _g(flow_iat.get("max", 0.0)),
            "flow_iat_min": _g(flow_iat.get("min", 0.0)),
            "flow_iat_std": _g(flow_iat.get("std", 0.0)),
            "fwd_iat_tot": _g(forward_iat.get("total", 0.0)),
            "fwd_iat_max": _g(forward_iat.get("max", 0.0)),
            "fwd_iat_min": _g(forward_iat.get("min", 0.0)),
            "fwd_iat_mean": _g(forward_iat.get("mean", 0.0)),
            "fwd_iat_std": _g(forward_iat.get("std", 0.0)),
            "bwd_iat_tot": _g(backward_iat.get("total", 0.0)),
            "bwd_iat_max": _g(backward_iat.get("max", 0.0)),
            "bwd_iat_min": _g(backward_iat.get("min", 0.0)),
            "bwd_iat_mean": _g(backward_iat.get("mean", 0.0)),
            "bwd_iat_std": _g(backward_iat.get("std", 0.0)),
            # Flags statistics
            "fwd_psh_flags": flag_count.has_flag("PSH", PacketDirection.FORWARD),
            "bwd_psh_flags": flag_count.has_flag("PSH", PacketDirection.REVERSE),
            "fwd_urg_flags": flag_count.has_flag("URG", PacketDirection.FORWARD),
            "bwd_urg_flags": flag_count.has_flag("URG", PacketDirection.REVERSE),
            "fin_flag_cnt": flag_count.has_flag("FIN"),
            "syn_flag_cnt": flag_count.has_flag("SYN"),
            "rst_flag_cnt": flag_count.has_flag("RST"),
            "psh_flag_cnt": flag_count.has_flag("PSH"),
            "ack_flag_cnt": flag_count.has_flag("ACK"),
            "urg_flag_cnt": flag_count.has_flag("URG"),
            "ece_flag_cnt": flag_count.has_flag("ECE"),
            # Response Time
            "down_up_ratio": packet_count.get_down_up_ratio(),
            "pkt_size_avg": _g(packet_length.get_avg()),
            "init_fwd_win_byts": _g(self.init_window_size.get(PacketDirection.FORWARD, 0)),
            "init_bwd_win_byts": _g(self.init_window_size.get(PacketDirection.REVERSE, 0)),
            "active_max": _g(active_stat.get("max", 0.0)),
            "active_min": _g(active_stat.get("min", 0.0)),
            "active_mean": _g(active_stat.get("mean", 0.0)),
            "active_std": _g(active_stat.get("std", 0.0)),
            "idle_max": _g(idle_stat.get("max", 0.0)),
            "idle_min": _g(idle_stat.get("min", 0.0)),
            "idle_mean": _g(idle_stat.get("mean", 0.0)),
            "idle_std": _g(idle_stat.get("std", 0.0)),
            "fwd_byts_b_avg": _g(flow_bytes.get_bytes_per_bulk(PacketDirection.FORWARD)),
            "fwd_pkts_b_avg": _g(flow_bytes.get_packets_per_bulk(PacketDirection.FORWARD)),
            "bwd_byts_b_avg": _g(flow_bytes.get_bytes_per_bulk(PacketDirection.REVERSE)),
            "bwd_pkts_b_avg": _g(flow_bytes.get_packets_per_bulk(PacketDirection.REVERSE)),
            "fwd_blk_rate_avg": _g(flow_bytes.get_bulk_rate(PacketDirection.FORWARD)),
            "bwd_blk_rate_avg": _g(flow_bytes.get_bulk_rate(PacketDirection.REVERSE)),
        }

        # Set default untuk protokol non-TCP
        if self.protocol != 6:  # 6 = TCP
            # Set semua flag TCP-related ke 0
            data.update(
                {
                    "fin_flag_cnt": 0,
                    "syn_flag_cnt": 0,
                    "rst_flag_cnt": 0,
                    "psh_flag_cnt": 0,
                    "ack_flag_cnt": 0,
                    "urg_flag_cnt": 0,
                    "ece_flag_cnt": 0,
                    "fwd_psh_flags": 0,
                    "bwd_psh_flags": 0,
                    "fwd_urg_flags": 0,
                    "bwd_urg_flags": 0,
                    "init_fwd_win_byts": 0,
                    "init_bwd_win_byts": 0,
                }
            )

        # Duplicated features
        data["fwd_seg_size_avg"] = data.get("fwd_pkt_len_mean", 0.0)
        data["bwd_seg_size_avg"] = data.get("bwd_pkt_len_mean", 0.0)
        data["cwe_flag_count"] = data.get("fwd_urg_flags", 0)
        data["subflow_fwd_pkts"] = data.get("tot_fwd_pkts", 0)
        data["subflow_bwd_pkts"] = data.get("tot_bwd_pkts", 0)
        data["subflow_fwd_byts"] = data.get("totlen_fwd_pkts", 0)
        data["subflow_bwd_byts"] = data.get("totlen_bwd_pkts", 0)

        return data

    def add_packet(self, packet: Any, direction: Enum) -> None:
        """Adds a packet to the current list of packets.

        Args:
            packet: Packet to be added to a flow
            direction: The direction the packet is going in that flow
        """
        self.packets.append((packet, direction))

        # Update flow dan subflow
        self.update_flow_bulk(packet, direction)
        self.update_subflow(packet)

        # Hitung interarrival time (safely)
        if self.start_timestamp != 0:
            try:
                # ensure numeric values are floats
                self.flow_interarrival_time.append(
                    1e6 * float(packet.time - float(self.latest_timestamp))
                )
            except Exception as e:
                # don't crash on a weird timestamp type
                print("[Warning] flow interarrival calc error:", e)
                self.flow_interarrival_time.append(0.0)

        # latest timestamp (ensure float)
        try:
            self.latest_timestamp = max([float(packet.time), float(self.latest_timestamp)])
        except Exception:
            # fallback
            self.latest_timestamp = float(packet.time)

        # TCP window size init (kalau ada)
        if packet.haslayer("TCP"):
            tcp_layer = packet.getlayer("TCP")
            if (
                direction == PacketDirection.FORWARD
                and self.init_window_size[direction] == 0
            ):
                self.init_window_size[direction] = tcp_layer.window
            elif direction == PacketDirection.REVERSE:
                self.init_window_size[direction] = tcp_layer.window

        # Tandai paket pertama
        if self.start_timestamp == 0:
            self.start_timestamp = float(packet.time)
            # protocol might be None; keep previous if not present
            self.protocol = packet.proto if hasattr(packet, "proto") else self.protocol

    def update_subflow(self, packet):
        """Update subflow

        Args:
            packet: Packet to be parse as subflow
        """
        last_timestamp = (
            self.latest_timestamp if self.latest_timestamp != 0 else packet.time
        )
        try:
            pkt_time = float(packet.time)
            last_ts = float(last_timestamp)
            if (pkt_time - (last_ts / 1e6)) > constants.CLUMP_TIMEOUT:
                self.update_active_idle(pkt_time - last_ts)
        except Exception as e:
            print("[Warning] update_subflow error:", e)

    def update_active_idle(self, current_time):
        """Adds a packet to the current list of packets.

        Args:
            current_time: current timestamp value (float seconds)
        """
        try:
            cur = float(current_time)
            last_act = float(self.last_active)
            if (cur - last_act) > constants.ACTIVE_TIMEOUT:
                duration = abs(float(self.last_active - self.start_active))
                if duration > 0:
                    self.active.append(1e6 * float(duration))
                self.idle.append(1e6 * float(cur - last_act))
                self.start_active = current_time
                self.last_active = current_time
            else:
                self.last_active = current_time
        except Exception as e:
            print("[Warning] update_active_idle error:", e)

    def update_flow_bulk(self, packet, direction):
        """Update bulk flow

        Args:
            packet: Packet to be parse as bulk
        """
        payload_size = len(PacketCount.get_payload(packet))
        if payload_size == 0:
            return
        if direction == PacketDirection.FORWARD:
            if self.backward_bulk_last_timestamp > self.forward_bulk_start_tmp:
                self.forward_bulk_start_tmp = 0
            if self.forward_bulk_start_tmp == 0:
                self.forward_bulk_start_tmp = float(packet.time)
                self.forward_bulk_last_timestamp = float(packet.time)
                self.forward_bulk_count_tmp = 1
                self.forward_bulk_size_tmp = payload_size
            else:
                if (float(packet.time) - float(self.forward_bulk_last_timestamp)) > constants.CLUMP_TIMEOUT:
                    self.forward_bulk_start_tmp = float(packet.time)
                    self.forward_bulk_last_timestamp = float(packet.time)
                    self.forward_bulk_count_tmp = 1
                    self.forward_bulk_size_tmp = payload_size
                else:  # Add to bulk
                    self.forward_bulk_count_tmp += 1
                    self.forward_bulk_size_tmp += payload_size
                    if self.forward_bulk_count_tmp == constants.BULK_BOUND:
                        self.forward_bulk_count += 1
                        self.forward_bulk_packet_count += self.forward_bulk_count_tmp
                        self.forward_bulk_size += self.forward_bulk_size_tmp
                        self.forward_bulk_duration += (
                            float(packet.time) - float(self.forward_bulk_start_tmp)
                        )
                    elif self.forward_bulk_count_tmp > constants.BULK_BOUND:
                        self.forward_bulk_packet_count += 1
                        self.forward_bulk_size += payload_size
                        self.forward_bulk_duration += (
                            float(packet.time) - float(self.forward_bulk_last_timestamp)
                        )
                    self.forward_bulk_last_timestamp = float(packet.time)
        else:
            if self.forward_bulk_last_timestamp > self.backward_bulk_start_tmp:
                self.backward_bulk_start_tmp = 0
            if self.backward_bulk_start_tmp == 0:
                self.backward_bulk_start_tmp = float(packet.time)
                self.backward_bulk_last_timestamp = float(packet.time)
                self.backward_bulk_count_tmp = 1
                self.backward_bulk_size_tmp = payload_size
            else:
                if (float(packet.time) - float(self.backward_bulk_last_timestamp)) > constants.CLUMP_TIMEOUT:
                    self.backward_bulk_start_tmp = float(packet.time)
                    self.backward_bulk_last_timestamp = float(packet.time)
                    self.backward_bulk_count_tmp = 1
                    self.backward_bulk_size_tmp = payload_size
                else:  # Add to bulk
                    self.backward_bulk_count_tmp += 1
                    self.backward_bulk_size_tmp += payload_size
                    if self.backward_bulk_count_tmp == constants.BULK_BOUND:
                        self.backward_bulk_count += 1
                        self.backward_bulk_packet_count += self.backward_bulk_count_tmp
                        self.backward_bulk_size += self.backward_bulk_size_tmp
                        self.backward_bulk_duration += (
                            float(packet.time) - float(self.backward_bulk_start_tmp)
                        )
                    elif self.backward_bulk_count_tmp > constants.BULK_BOUND:
                        self.backward_bulk_packet_count += 1
                        self.backward_bulk_size += payload_size
                        self.backward_bulk_duration += (
                            float(packet.time) - float(self.backward_bulk_last_timestamp)
                        )
                    self.backward_bulk_last_timestamp = float(packet.time)

    @property
    def duration(self):
        return float(self.latest_timestamp) - float(self.start_timestamp)
