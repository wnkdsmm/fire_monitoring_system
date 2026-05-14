Option Explicit

Dim shell, fso, projectRoot, logsDir, logFilePath
Dim envFilePath, envVars, appHost, appPort, clearUrl
Dim responseText, statusCode, ok

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
logsDir = fso.BuildPath(projectRoot, "logs")
If Not fso.FolderExists(logsDir) Then
    On Error Resume Next
    fso.CreateFolder logsDir
    On Error GoTo 0
End If
logFilePath = fso.BuildPath(logsDir, "clear_cache.log")

envFilePath = fso.BuildPath(projectRoot, ".env")
Set envVars = LoadEnvFile(envFilePath)
appHost = GetEnvOrDefault(envVars, "APP_HOST", "127.0.0.1")
appPort = GetEnvOrDefault(envVars, "APP_PORT", "8000")
clearUrl = "http://" & appHost & ":" & appPort & "/api/admin/clear-cache"

LogMessage "==== clear-cache begin ===="
LogMessage "URL: " & clearUrl

ok = PostJson(clearUrl, "{}", statusCode, responseText)

If ok And statusCode >= 200 And statusCode < 300 Then
    LogMessage "SUCCESS status=" & CStr(statusCode)
    LogMessage "Response: " & responseText
    MsgBox "Cache cleared." & vbCrLf & "HTTP " & CStr(statusCode), vbInformation, "Fire Data"
    WScript.Quit 0
End If

LogMessage "ERROR status=" & CStr(statusCode)
LogMessage "Response/Error: " & responseText
MsgBox "Failed to clear cache." & vbCrLf & _
       "Ensure the app is running." & vbCrLf & _
       "URL: " & clearUrl & vbCrLf & _
       "HTTP: " & CStr(statusCode), vbExclamation, "Fire Data"
WScript.Quit 1

Function PostJson(url, body, ByRef statusCode, ByRef responseText)
    Dim request
    statusCode = 0
    responseText = ""
    On Error Resume Next
    Set request = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    request.setTimeouts 1000, 1000, 5000, 5000
    request.open "POST", url, False
    request.setRequestHeader "Content-Type", "application/json"
    request.setRequestHeader "Accept", "application/json"
    request.send body
    If Err.Number <> 0 Then
        responseText = "Request error: " & Err.Description
        Err.Clear
        PostJson = False
        On Error GoTo 0
        Exit Function
    End If
    statusCode = request.status
    responseText = request.responseText
    PostJson = True
    On Error GoTo 0
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
