import subprocess
result = subprocess.run(
    ["ping","192.168.100.1","-n","1"],
    capture_output=True,
    text=True
)
print(result.stdout)
print("Reply" in result.stdout)