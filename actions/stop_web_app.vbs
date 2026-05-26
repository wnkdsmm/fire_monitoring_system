Option Explicit

Dim shell, fso, projectRoot, logsDir, logFilePath, silentSuccess
Dim envFilePath, envVars, appPort
Dim stoppedByName, stoppedByPort, cacheRemoved

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
silentSuccess = (LCase(Trim(GetArg(0))) = "--silent-success")

projectRoot = ResolveProjectRoot()
logsDir = fso.BuildPath(projectRoot, "logs")
If Not fso.FolderExists(logsDir) Then
    On Error Resume Next
    fso.CreateFolder logsDir
    On Error GoTo 0
End If
logFilePath = fso.BuildPath(logsDir, "shutdown.log")

LogMessage "==== shutdown begin ===="
LogMessage "Project root: " & projectRoot

envFilePath = fso.BuildPath(projectRoot, ".env")
Set envVars = LoadEnvFile(envFilePath)
appPort = GetEnvOrDefault(envVars, "APP_PORT", "8000")

stoppedByName = StopUvicornPython()
stoppedByPort = StopByPortRange(appPort, 20)
cacheRemoved = ClearCaches(projectRoot)

LogMessage "Stopped by name: " & CStr(stoppedByName)
LogMessage "Stopped by port: " & CStr(stoppedByPort)
LogMessage "Cache entries removed: " & CStr(cacheRemoved)
LogMessage "==== shutdown complete ===="

If Not silentSuccess Then
    Notify "Server stop complete." & vbCrLf & _
           "Stopped by name: " & CStr(stoppedByName) & vbCrLf & _
           "Stopped by port: " & CStr(stoppedByPort) & vbCrLf & _
           "Cache removed: " & CStr(cacheRemoved), vbInformation, "Fire Data"
End If

Function GetArg(index)
    If WScript.Arguments.Count > index Then
        GetArg = WScript.Arguments(index)
    Else
        GetArg = ""
    End If
End Function

Function ResolveProjectRoot()
    Dim scriptDir
    scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
    If LCase(fso.GetFileName(scriptDir)) = "actions" Then
        ResolveProjectRoot = fso.GetParentFolderName(scriptDir)
    Else
        ResolveProjectRoot = scriptDir
    End If
End Function

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function

Function StopUvicornPython()
    Dim wmi, processes, proc, cmdLine, killed
    killed = 0

    On Error Resume Next
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    If Err.Number <> 0 Then
        Err.Clear
        StopUvicornPython = 0
        On Error GoTo 0
        Exit Function
    End If
    On Error GoTo 0

    Set processes = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'")
    For Each proc In processes
        cmdLine = ""
        On Error Resume Next
        cmdLine = LCase(CStr(proc.CommandLine))
        On Error GoTo 0

        If InStr(cmdLine, "uvicorn") > 0 Or InStr(cmdLine, "app.main:app") > 0 Then
            If KillPid(CLng(proc.ProcessId)) Then killed = killed + 1
        End If
    Next

    StopUvicornPython = killed
End Function

Function StopByPortRange(preferredPort, maxAttempts)
    Dim i, portCandidate, pids, pid, killed
    killed = 0

    For i = 0 To maxAttempts
        portCandidate = CStr(CLng(preferredPort) + i)
        Set pids = PidsListeningOnPort(portCandidate)
        For Each pid In pids.Keys
            If KillPid(CLng(pid)) Then killed = killed + 1
        Next
    Next

    StopByPortRange = killed
End Function

Function PidsListeningOnPort(portValue)
    Dim dict, exec, text, lines, line, parts, pid
    Set dict = CreateObject("Scripting.Dictionary")

    On Error Resume Next
    Set exec = shell.Exec("cmd /c netstat -ano -p tcp | findstr LISTENING | findstr /c:" & Quote(":" & portValue & " "))
    If Err.Number <> 0 Then
        Err.Clear
        Set PidsListeningOnPort = dict
        On Error GoTo 0
        Exit Function
    End If
    On Error GoTo 0

    text = exec.StdOut.ReadAll
    exec.StdErr.ReadAll
    If Len(text) = 0 Then
        Set PidsListeningOnPort = dict
        Exit Function
    End If

    lines = Split(text, vbCrLf)
    For Each line In lines
        line = Trim(line)
        If Len(line) > 0 Then
            parts = SplitOnWhitespace(line)
            If UBound(parts) >= 4 Then
                pid = parts(UBound(parts))
                If IsNumeric(pid) Then
                    If Not dict.Exists(pid) Then dict.Add pid, True
                End If
            End If
        End If
    Next

    Set PidsListeningOnPort = dict
End Function

Function SplitOnWhitespace(textLine)
    Dim i, ch, token, out()
    ReDim out(-1)
    token = ""

    For i = 1 To Len(textLine)
        ch = Mid(textLine, i, 1)
        If ch = " " Or ch = vbTab Then
            If Len(token) > 0 Then
                ReDim Preserve out(UBound(out) + 1)
                out(UBound(out)) = token
                token = ""
            End If
        Else
            token = token & ch
        End If
    Next

    If Len(token) > 0 Then
        ReDim Preserve out(UBound(out) + 1)
        out(UBound(out)) = token
    End If

    If UBound(out) < 0 Then
        ReDim out(0)
        out(0) = ""
    End If
    SplitOnWhitespace = out
End Function

Function KillPid(pidValue)
    Dim code
    code = shell.Run("cmd /c taskkill /PID " & CStr(pidValue) & " /F >nul 2>nul", 0, True)
    KillPid = (code = 0)
End Function

Function ClearCaches(rootPath)
    Dim removed
    removed = 0
    removed = removed + RemoveFolderIfExists(fso.BuildPath(rootPath, ".pytest_cache"))
    removed = removed + RemoveFolderIfExists(fso.BuildPath(rootPath, "__pycache__"))
    removed = removed + RemovePyCacheFoldersRecursively(rootPath)
    removed = removed + RemoveFilesByExtension(rootPath, "pyc")
    removed = removed + RemoveFilesByExtension(rootPath, "pyo")
    ClearCaches = removed
End Function

Function RemoveFolderIfExists(folderPath)
    If fso.FolderExists(folderPath) Then
        On Error Resume Next
        fso.DeleteFolder folderPath, True
        If Err.Number = 0 Then
            RemoveFolderIfExists = 1
            LogMessage "Removed folder: " & folderPath
        Else
            LogMessage "WARN: failed to remove folder: " & folderPath & " | " & Err.Description
            Err.Clear
            RemoveFolderIfExists = 0
        End If
        On Error GoTo 0
    Else
        RemoveFolderIfExists = 0
    End If
End Function

Function RemovePyCacheFoldersRecursively(rootPath)
    Dim removed
    removed = 0
    On Error Resume Next
    removed = RemovePyCacheInFolder(fso.GetFolder(rootPath))
    If Err.Number <> 0 Then
        LogMessage "WARN: recursive cache cleanup failed: " & Err.Description
        Err.Clear
    End If
    On Error GoTo 0
    RemovePyCacheFoldersRecursively = removed
End Function

Function RemovePyCacheInFolder(folderObj)
    Dim subFolder, removed
    removed = 0

    For Each subFolder In folderObj.SubFolders
        If LCase(subFolder.Name) = "__pycache__" Then
            On Error Resume Next
            fso.DeleteFolder subFolder.Path, True
            If Err.Number = 0 Then
                removed = removed + 1
                LogMessage "Removed folder: " & subFolder.Path
            Else
                LogMessage "WARN: failed to remove folder: " & subFolder.Path & " | " & Err.Description
                Err.Clear
            End If
            On Error GoTo 0
        ElseIf LCase(subFolder.Name) <> ".git" And LCase(subFolder.Name) <> ".venv" Then
            removed = removed + RemovePyCacheInFolder(subFolder)
        End If
    Next

    RemovePyCacheInFolder = removed
End Function

Function RemoveFilesByExtension(rootPath, extNoDot)
    Dim removed
    removed = 0
    On Error Resume Next
    removed = RemoveFilesInFolderByExtension(fso.GetFolder(rootPath), LCase(extNoDot))
    If Err.Number <> 0 Then
        LogMessage "WARN: file cache cleanup failed for ." & extNoDot & ": " & Err.Description
        Err.Clear
    End If
    On Error GoTo 0
    RemoveFilesByExtension = removed
End Function

Function RemoveFilesInFolderByExtension(folderObj, extNoDot)
    Dim subFolder, fileObj, removed, fileExt
    removed = 0

    For Each fileObj In folderObj.Files
        fileExt = LCase(fso.GetExtensionName(fileObj.Name))
        If fileExt = extNoDot Then
            On Error Resume Next
            fileObj.Delete True
            If Err.Number = 0 Then
                removed = removed + 1
                LogMessage "Removed file: " & fileObj.Path
            Else
                LogMessage "WARN: failed to remove file: " & fileObj.Path & " | " & Err.Description
                Err.Clear
            End If
            On Error GoTo 0
        End If
    Next

    For Each subFolder In folderObj.SubFolders
        If LCase(subFolder.Name) <> ".git" And LCase(subFolder.Name) <> ".venv" Then
            removed = removed + RemoveFilesInFolderByExtension(subFolder, extNoDot)
        End If
    Next

    RemoveFilesInFolderByExtension = removed
End Function

Function LoadEnvFile(filePath)
    Dim dict, fileHandle, lineText, eqPos, keyName, valueText
    Set dict = CreateObject("Scripting.Dictionary")

    If Not fso.FileExists(filePath) Then
        Set LoadEnvFile = dict
        Exit Function
    End If

    On Error Resume Next
    Set fileHandle = fso.OpenTextFile(filePath, 1, False)
    If Err.Number <> 0 Then
        Err.Clear
        On Error GoTo 0
        Set LoadEnvFile = dict
        Exit Function
    End If
    On Error GoTo 0

    Do Until fileHandle.AtEndOfStream
        lineText = Trim(fileHandle.ReadLine)
        If Len(lineText) = 0 Then
            ' skip
        ElseIf Left(lineText, 1) = "#" Then
            ' skip
        Else
            eqPos = InStr(1, lineText, "=", vbTextCompare)
            If eqPos > 1 Then
                keyName = Trim(Left(lineText, eqPos - 1))
                valueText = Trim(Mid(lineText, eqPos + 1))
                valueText = StripWrappingQuotes(valueText)
                If Len(keyName) > 0 Then
                    If dict.Exists(keyName) Then
                        dict(keyName) = valueText
                    Else
                        dict.Add keyName, valueText
                    End If
                End If
            End If
        End If
    Loop
    fileHandle.Close
    Set LoadEnvFile = dict
End Function

Function StripWrappingQuotes(valueText)
    Dim outValue
    outValue = valueText
    If Len(outValue) >= 2 Then
        If (Left(outValue, 1) = Chr(34) And Right(outValue, 1) = Chr(34)) Or (Left(outValue, 1) = "'" And Right(outValue, 1) = "'") Then
            outValue = Mid(outValue, 2, Len(outValue) - 2)
        End If
    End If
    StripWrappingQuotes = outValue
End Function

Function GetEnvOrDefault(envDict, keyName, defaultValue)
    If Not envDict Is Nothing Then
        If envDict.Exists(keyName) Then
            GetEnvOrDefault = envDict(keyName)
            Exit Function
        End If
    End If
    GetEnvOrDefault = defaultValue
End Function

Sub LogMessage(messageText)
    Dim fileHandle, lineText
    lineText = FormatDateTime(Now, 2) & " " & FormatDateTime(Now, 4) & " | " & messageText
    On Error Resume Next
    Set fileHandle = fso.OpenTextFile(logFilePath, 8, True)
    If Err.Number = 0 Then
        fileHandle.WriteLine lineText
        fileHandle.Close
    Else
        Err.Clear
    End If
    On Error GoTo 0
End Sub

Sub Notify(text, flags, title)
    CreateObject("WScript.Shell").Popup text, 5, title, flags
End Sub
