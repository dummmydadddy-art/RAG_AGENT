@echo off
title EduConnect LMS Shutdown
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-services.ps1"
