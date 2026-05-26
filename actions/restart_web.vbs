Option Explicit

Dim shell, fso, projectRoot, stopScript, startScript, cmdStop, cmdStart, rc

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
stopScript = fso.BuildPath(projectRoot, "stop_web_app.vbs")
startScript = fso.BuildPath(projectRoot, "start_web.vbs")

If Not fso.FileExists(stopScript) Then
    Notify "Not found: " & stopScript, vbCritical, "Fire Data"
    WScript.Quit 1
End If

If Not fso.FileExists(startScript) Then
    Notify "Not found: " & startScript, vbCritical, "Fire Data"
    WScript.Quit 1
End If

cmdStop = "cscript //nologo """ & stopScript & """ --silent-success"
cmdStart = "cscript //nologo """ & startScript & """ --silent-success"

' stop_web_app.vbs already performs cache cleanup.
rc = shell.Run(cmdStop, 0, True)
If rc <> 0 Then
    Notify "Stop failed. Code: " & CStr(rc), vbCritical, "Fire Data"
    WScript.Quit rc
End If

rc = shell.Run(cmdStart, 0, True)
If rc <> 0 Then
    Notify "Start failed. Code: " & CStr(rc), vbCritical, "Fire Data"
    WScript.Quit rc
End If

Notify "Restart complete. Cache cleared.", vbInformation, "Fire Data"
WScript.Quit 0

Sub Notify(text, flags, title)
    CreateObject("WScript.Shell").Popup text, 5, title, flags
End Sub

