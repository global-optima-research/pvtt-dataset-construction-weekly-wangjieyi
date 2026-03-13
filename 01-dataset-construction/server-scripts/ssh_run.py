"""SSH helper for running commands on the 5090 server."""

import paramiko
import sys

HOST = "111.17.197.107"
USER = "wangjieyi"
PASS = "wangjieyi@hkust"

def ssh_exec(cmd, timeout=300):
    """Execute a command on the remote server and print output."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    if out:
        print(out)
    if err:
        print("STDERR:", err, file=sys.stderr)
    return out, err

def ssh_upload(local_path, remote_path):
    """Upload a file to the remote server via SFTP."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    ssh.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        ssh_exec(cmd)
    else:
        print("Usage: python ssh_run.py <command>")
