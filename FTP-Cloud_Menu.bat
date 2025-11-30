@echo off
title FTP CLOUD  USER-MANAGER
color 0A

echo =============================================
echo      Connecting to FTP CLOUD...
echo =============================================
echo.

ssh -t -o StrictHostKeyChecking=no root@192.168.1.8 "/bin/bash /root/FTP_Cloud_v1.2/ftpmenuv1.2.sh"

echo.
echo =============================================
echo   Session Closed. Press any key to exit
echo =============================================
pause >nul
