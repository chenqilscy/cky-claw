"""检查 admin sudo 权限并添加到 docker group。"""
import paramiko

HOST = "fn.cky"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username="admin", password="cky.my.2", timeout=10)

# 检查 sudo 可用性
print("[*] Checking sudo access...")
stdin, stdout, stderr = ssh.exec_command("echo 'cky.my.2' | sudo -S id 2>&1")
rc = stdout.channel.recv_exit_status()
out = stdout.read().decode().strip()
print(f"  sudo id: {out} (rc={rc})")

# 检查 docker 是否安装
print("[*] Checking if docker is installed...")
stdin, stdout, stderr = ssh.exec_command("echo 'cky.my.2' | sudo -S docker version --format '{{.Server.Version}}' 2>&1")
rc = stdout.channel.recv_exit_status()
out = stdout.read().decode().strip()
print(f"  docker version: {out} (rc={rc})")

# 尝试添加到 docker group
print("[*] Adding admin to docker group...")
stdin, stdout, stderr = ssh.exec_command("echo 'cky.my.2' | sudo -S usermod -aG docker admin 2>&1")
rc = stdout.channel.recv_exit_status()
out = stdout.read().decode().strip()
print(f"  usermod: {out} (rc={rc})")

# 检查当前 groups
stdin, stdout, stderr = ssh.exec_command("groups")
out = stdout.read().decode().strip()
print(f"  current groups: {out}")

ssh.close()
