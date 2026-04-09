"""远程 Docker 配置脚本。"""
import paramiko
import os
import sys

HOST = "fn.cky"
ADMIN_USER = "admin"
ADMIN_PASS = "cky.my.2"
ROOT_USER = "root"
ROOT_PASS = "root"

def deploy_ssh_key():
    """部署 SSH 公钥到远程服务器。"""
    pub_key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
    with open(pub_key_path) as f:
        pub_key = f.read().strip()

    for user, pwd in [(ADMIN_USER, ADMIN_PASS), (ROOT_USER, ROOT_PASS)]:
        print(f"[*] Deploying SSH key for {user}@{HOST}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(HOST, username=user, password=pwd, timeout=10)
        except Exception as e:
            print(f"  [-] Connect failed: {e}")
            continue

        cmds = [
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh",
            f'grep -qF "{pub_key}" ~/.ssh/authorized_keys 2>/dev/null || echo "{pub_key}" >> ~/.ssh/authorized_keys',
            "chmod 600 ~/.ssh/authorized_keys",
        ]
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()

        print(f"  [+] SSH key deployed for {user}")
        ssh.close()


def check_docker_and_fix():
    """检查 Docker 权限并修复。"""
    # 先用 admin 检查
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=ADMIN_USER, password=ADMIN_PASS, timeout=10)

    stdin, stdout, stderr = ssh.exec_command("docker version --format '{{.Server.Version}}'")
    rc = stdout.channel.recv_exit_status()
    if rc == 0:
        ver = stdout.read().decode().strip()
        print(f"[+] Docker OK (admin): {ver}")
        ssh.close()
        return True

    err = stderr.read().decode().strip()
    print(f"[-] Docker access denied for admin: {err}")
    ssh.close()

    # 用 root 添加 admin 到 docker group
    print("[*] Adding admin to docker group via root...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, username=ROOT_USER, password=ROOT_PASS, timeout=10)
    except Exception as e:
        print(f"[-] Root login failed: {e}")
        return False

    stdin, stdout, stderr = ssh.exec_command("usermod -aG docker admin")
    rc = stdout.channel.recv_exit_status()
    if rc == 0:
        print("[+] admin added to docker group")
    else:
        print(f"[-] Failed: {stderr.read().decode().strip()}")

    # 验证 root docker 可用
    stdin, stdout, stderr = ssh.exec_command("docker version --format '{{.Server.Version}}'")
    rc = stdout.channel.recv_exit_status()
    ver = stdout.read().decode().strip()
    print(f"[+] Docker (root): {ver}")
    ssh.close()

    return True


def setup_docker_context():
    """提示用户设置 Docker context。"""
    print("\n[*] To use remote Docker, run:")
    print(f"  docker context create remote --docker 'host=ssh://admin@{HOST}'")
    print("  docker context use remote")
    print("  (Note: admin must be in docker group, re-login may be needed)")


if __name__ == "__main__":
    deploy_ssh_key()
    check_docker_and_fix()
    setup_docker_context()
