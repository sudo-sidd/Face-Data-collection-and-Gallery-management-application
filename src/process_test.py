import psutil
import time
import csv
import subprocess

# 🔁 Change this to your actual Flask app PID
FLASK_PID = 57507

# Function to get GPU usage using nvidia-smi
def get_gpu_usage():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,nounits,noheader"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        output = result.stdout.strip().split("\n")
        # In case of multiple GPUs, sum usage
        total_used, total_mem, total_util = 0, 0, 0
        for line in output:
            used, total, util = map(int, line.split(","))
            total_used += used
            total_mem += total
            total_util += util
        return round(total_used, 2), round(total_mem, 2), round(total_util / max(len(output), 1), 2)
    except Exception as e:
        print("⚠️ GPU info error:", e)
        return 0, 0, 0

try:
    proc = psutil.Process(FLASK_PID)
except psutil.NoSuchProcess:
    print(f"❌ No process found with PID {FLASK_PID}")
    exit()

print("🟢 Monitoring started. Ctrl+C to stop.")

with open("flask_full_usage_log.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Time (s)", "CPU (%)", "RAM (MB)", 
        "Disk Read (MB)", "Disk Write (MB)", 
        "GPU Used (MB)", "GPU Total (MB)", "GPU Utilization (%)"
    ])

    start = time.time()
    while True:
        t = round(time.time() - start, 2)
        cpu = proc.cpu_percent(interval=1)
        ram = proc.memory_info().rss / 1024**2

        io_counters = proc.io_counters()
        read_mb = io_counters.read_bytes / 1024**2
        write_mb = io_counters.write_bytes / 1024**2

        gpu_used, gpu_total, gpu_util = get_gpu_usage()

        writer.writerow([t, cpu, round(ram, 2), round(read_mb, 2), round(write_mb, 2), gpu_used, gpu_total, gpu_util])

        print(f"⏱️ {t}s | 🧠 CPU: {cpu}% | 💾 RAM: {round(ram,2)}MB | 📦 Read: {round(read_mb,2)}MB | ✍️ Write: {round(write_mb,2)}MB | 🖥️ GPU: {gpu_used}/{gpu_total}MB ({gpu_util}%)")
