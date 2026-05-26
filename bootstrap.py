import subprocess



cmd = ".\\tor.exe -f .\\torrc"



subprocess.Popen(cmd, shell = True, creationflags=subprocess.CREATE_NO_WINDOW)