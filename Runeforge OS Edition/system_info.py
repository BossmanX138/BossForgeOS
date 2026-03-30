import platform
import psutil

def get_system_info():
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"CPU: {platform.processor()}")
    print(f"RAM: {psutil.virtual_memory().total // (1024*1024)} MB")
    print(f"Disk: {psutil.disk_usage('/').total // (1024*1024*1024)} GB total")

if __name__ == "__main__":
    get_system_info()
