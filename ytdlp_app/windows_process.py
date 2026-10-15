"""Windows job objects: own a command and everything it starts, independently of its pid.

A child is started suspended, put in a fresh job before any of its code runs, and only then
resumed; whatever it starts (yt-dlp starts ffmpeg) is in the same job. The job can then be
terminated as a whole, also after the process that started the rest has left, which a
``taskkill /T`` on that process's pid cannot do. Closing the job's last handle kills what is
still in it as well (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE), so not even a crash of this program
leaves a stray ffmpeg behind.

Only documented Win32 calls through ctypes are used, and nothing private to subprocess.Popen.
"""

from __future__ import annotations

import sys
import threading

#: Popen creationflags that start the child suspended: ProcessJob.adopt resumes it.
CREATE_SUSPENDED = 0x00000004

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100
    _SYNCHRONIZE = 0x00100000
    _THREAD_SUSPEND_RESUME = 0x0002
    _TH32CS_SNAPTHREAD = 0x00000004
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
    _WAIT_OBJECT_0 = 0
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    #: How often the leader watch looks up to see whether the job is being closed.
    _WATCH_POLL_MS = 100

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    def _declare(name: str, restype: object, *argtypes: object) -> None:
        function = getattr(_kernel32, name)
        function.restype = restype
        function.argtypes = list(argtypes)

    _declare("CreateJobObjectW", wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCWSTR)
    _declare(
        "SetInformationJobObject",
        wintypes.BOOL,
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    _declare("AssignProcessToJobObject", wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE)
    _declare("TerminateJobObject", wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
    _declare("OpenProcess", wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _declare("TerminateProcess", wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
    _declare("OpenThread", wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _declare("ResumeThread", wintypes.DWORD, wintypes.HANDLE)
    _declare("CreateToolhelp32Snapshot", wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
    _declare("Thread32First", wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _declare("Thread32Next", wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _declare("WaitForSingleObject", wintypes.DWORD, wintypes.HANDLE, wintypes.DWORD)
    _declare("CloseHandle", wintypes.BOOL, wintypes.HANDLE)

    def _error(what: str) -> OSError:
        code = ctypes.get_last_error()
        return OSError(code, f"{what} failed: {ctypes.FormatError(code).strip()}")

    def _resume_threads(pid: int) -> int:
        """Resume every thread of process `pid` (a process started suspended has one).
        Returns how many were resumed."""
        snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
            raise _error("CreateToolhelp32Snapshot")
        resumed = 0
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(_ThreadEntry)
            more = _kernel32.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == pid:
                    thread = _kernel32.OpenThread(_THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                    if not thread:
                        raise _error("OpenThread")
                    try:
                        if _kernel32.ResumeThread(thread) == 0xFFFFFFFF:
                            raise _error("ResumeThread")
                    finally:
                        _kernel32.CloseHandle(thread)
                    resumed += 1
                more = _kernel32.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            _kernel32.CloseHandle(snapshot)
        return resumed

    class ProcessJob:
        """The job holding one command's process tree.

        A watch thread waits for the command's own process to leave and then terminates
        the job: what it left behind (an ffmpeg, a helper holding the output pipe open)
        goes with it, so the caller's read of the output ends and nothing is orphaned.
        """

        def __init__(self, job: int, process: int) -> None:
            self._job: int | None = job
            self._process: int | None = process
            self._lock = threading.Lock()
            self._closing = threading.Event()
            self._watch = threading.Thread(
                target=self._sweep_when_leader_leaves, name="job-watch", daemon=True
            )
            self._watch.start()

        @staticmethod
        def adopt(pid: int) -> ProcessJob:
            """Put the suspended process `pid` in a new job and resume it.

            Raises OSError, after terminating the still suspended process, when any step
            fails: a command whose tree could not be put under control must not run.
            """
            process = _kernel32.OpenProcess(
                _PROCESS_TERMINATE | _PROCESS_SET_QUOTA | _SYNCHRONIZE, False, pid
            )
            if not process:
                raise _error("OpenProcess")
            job = None
            try:
                job = _kernel32.CreateJobObjectW(None, None)
                if not job:
                    raise _error("CreateJobObjectW")
                limits = _ExtendedLimits()
                limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if not _kernel32.SetInformationJobObject(
                    job,
                    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                    ctypes.byref(limits),
                    ctypes.sizeof(limits),
                ):
                    raise _error("SetInformationJobObject")
                if not _kernel32.AssignProcessToJobObject(job, process):
                    raise _error("AssignProcessToJobObject")
                if _resume_threads(pid) == 0:
                    raise OSError(f"ResumeThread failed: no thread of process {pid} was found")
            except BaseException:
                _kernel32.TerminateProcess(process, 1)
                _kernel32.CloseHandle(process)
                if job:
                    _kernel32.CloseHandle(job)
                raise
            return ProcessJob(job, process)

        def _sweep_when_leader_leaves(self) -> None:
            while not self._closing.is_set():
                with self._lock:
                    if self._process is None:
                        return
                    left = _kernel32.WaitForSingleObject(self._process, 0) == _WAIT_OBJECT_0
                if left:
                    self.terminate()
                    return
                self._closing.wait(_WATCH_POLL_MS / 1000)

        def terminate(self) -> None:
            """Kill everything still in the job; nothing to do once it is closed."""
            with self._lock:
                if self._job is not None:
                    _kernel32.TerminateJobObject(self._job, 1)

        def close(self) -> None:
            """Kill what is left and release the handles. Safe to call again, and from
            several threads."""
            self._closing.set()
            if threading.current_thread() is not self._watch:
                self._watch.join()
            with self._lock:
                job, process = self._job, self._process
                self._job = self._process = None
            if job is not None:
                _kernel32.TerminateJobObject(job, 1)
                _kernel32.CloseHandle(job)
            if process is not None:
                _kernel32.CloseHandle(process)
