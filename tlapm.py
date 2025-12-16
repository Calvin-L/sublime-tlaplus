import threading
import subprocess
import traceback
import re
from collections import namedtuple
import os
import random
import shlex

import sublime
import sublime_plugin


TLAPM_EXECUTABLE = "tlapm"
TLAPM_ARGV = []
ESCAPE_SEQ = re.compile(r"^" + re.escape("@!!") + r"(\w+)", re.MULTILINE)
MISSING_OBLIGATION = re.compile(r"^\s*missing_proof.*?at line (\d+), characters? (\d+)(?:-(\d+))?$", re.MULTILINE)
# INFO_PATTERN = re.compile(r"^" + re.escape("@!!") + r"([^:]*?)" + re.escape(":") + r"(.*)$")
SPAN_PATTERN = re.compile(r"^(\d+):(\d+):(\d+):(\d+)$")
TLAPM_STATUS_KEY = "tlapm_status"
Posn = namedtuple("Posn", ["line", "column"])
Span = namedtuple("Span", ["start", "end"])


workers = []
dirty_buffers_monitor = threading.Condition()
dirty_buffers = {}
running = True


def plugin_loaded():
    print("---- LOADING TLAPS PLUGIN ----")
    workers.append(Worker())


def plugin_unloaded():
    global running
    print("---- UNLOADING TLAPS PLUGIN ----")
    with dirty_buffers_monitor:
        running = False
        dirty_buffers_monitor.notify_all()
    for w in workers:
        w.interrupt()
    for w in workers:
        w.join()
    workers.clear()


class Worker(object):

    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._phantom_set_by_view = {}
        self._thread = threading.Thread(target=self._bg_job)
        self._thread.start()

    # Interaction with background thread

    def interrupt(self):
        with self._lock:
            if (p := self._proc) is not None:
                p.terminate()

    def join(self):
        self._thread.join()

    # Background thread

    def _bg_job(self):
        print("Starting {}...".format(self))

        run = True
        while run:

            # attempt to pick a job
            with dirty_buffers_monitor:
                while not dirty_buffers and running:
                    dirty_buffers_monitor.wait()
                run = running
                if run:
                    (buffer_id, (buffer, file)) = random.choice(list(dirty_buffers.items()))
                    del dirty_buffers[buffer_id]

            if not run:
                break

            print("Dirty: {} [{}]".format(buffer, file))

            self._display_proof_in_progress(buffer)

            proc = None
            with self._lock:

                with dirty_buffers_monitor:
                    run = running

                if run:
                    dir_name = os.path.dirname(file)
                    file_name = os.path.basename(file)
                    cmd1 = shlex.join([TLAPM_EXECUTABLE] + TLAPM_ARGV + ["--summary",           file_name])
                    cmd2 = shlex.join([TLAPM_EXECUTABLE] + TLAPM_ARGV + ["--toolbox", "0", "0", file_name])
                    proc = subprocess.Popen(
                        ["bash", "-c", cmd1 + " && " + cmd2],
                        cwd=os.path.abspath(dir_name),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL)

                self._proc = proc

            if proc is not None:
                try:
                    print("Waiting for output...")
                    output = b""
                    buf = None
                    while buf := proc.stdout.read(8192):
                        # print(buf)
                        output += buf
                    proc.wait()
                    print("tlapm returned code {}".format(proc.returncode))
                    if proc.returncode == 0:
                        self._display_proof_state(buffer, self._parse_output(output))
                    else:
                        print(output)
                        self._clear_proof_state(buffer)
                except Exception:
                    traceback.print_exc()
                    self._clear_proof_state(buffer)

        print("Stopping thread for {}...".format(self))

    def _parse_output(self, output: bytes):
        output = output.decode("utf-8")
        result = []

        for match in MISSING_OBLIGATION.finditer(output):
            line = int(match.group(1))
            col_start = int(match.group(2))
            col_end = int(match.group(3)) if match.group(3) else col_start
            result.append({"type": "missing_proof", "loc": Span(
                start=Posn(line=line, column=col_start),
                end=Posn(line=line, column=col_end))})

        info = None
        prev_phrase = None
        for match in ESCAPE_SEQ.finditer(output):
            phrase = match.group(1)
            if phrase == "BEGIN":
                info = {}
            else:
                if prev_phrase is not None:
                    val = output[start_index+1:match.start()].strip()
                    if prev_phrase == "loc":
                        val = self._parse_span(val)
                    info[prev_phrase] = val
                if phrase == "END":
                    result.append(info)
                    info = None
                    prev_phrase = None
                else:
                    start_index = match.end()
                    prev_phrase = match.group(1)
        return result

    def _parse_span(self, val):
        m = SPAN_PATTERN.match(val)
        return Span(
            start=Posn(line=int(m.group(1)), column=int(m.group(2))),
            end=Posn(line=int(m.group(3)), column=int(m.group(4))))

    def _display_proof_in_progress(self, buffer):
        sublime.set_timeout(lambda: self._display_proof_in_progress_on_main_thread(buffer))

    def _display_proof_state(self, buffer, infos):
        sublime.set_timeout(lambda: self._display_proof_state_on_main_thread(buffer, infos))

    def _clear_proof_state(self, buffer):
        sublime.set_timeout(lambda: self._clear_proof_state_on_main_thread(buffer))

    def _display_proof_in_progress_on_main_thread(self, buffer):
        for view in buffer.views():
            view.set_status(TLAPM_STATUS_KEY, "Checking proofs...")
        self._clear_proof_state_on_main_thread(buffer)

    def _find_phantom_set_on_main_thread(self, view):
        key = view.id()
        res = self._phantom_set_by_view.get(key)
        if res is None:
            res = sublime.PhantomSet(view, "TLA+Proofs")
            self._phantom_set_by_view[key] = res
        return res

    def _display_proof_state_on_main_thread(self, buffer, infos):
        obligations = {}
        for info in infos:
            # print(info)
            if info.get("type") == "obligation":
                obligations[info.get("id")] = info

        good_ranges = []
        bad_ranges = []
        phantoms = []
        for info in obligations.values():
            span = info["loc"]
            status = info["status"]
            start = buffer.primary_view().text_point(row=span.start.line-1, col=span.start.column-1)
            end = buffer.primary_view().text_point(row=span.end.line-1, col=span.end.column-1)
            if status == "proved":
                good_ranges.append(sublime.Region(start, end))
            elif status == "failed":
                region = sublime.Region(start, end)
                bad_ranges.append(region)
                obligation_html = (info["obl"]
                    .replace("&", "&amp;")
                    .replace(" ", "&nbsp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>"))
                phantoms.append(sublime.Phantom(region=region, content=f"<body><style>body {{ background-color: color(red alpha(0.25)); padding: 0.5em; }}</style>{obligation_html}</body>", layout=sublime.PhantomLayout.BELOW))

        for info in infos:
            if info.get("type") == "missing_proof":
                span = info["loc"]
                start = buffer.primary_view().text_point(row=span.start.line-1, col=span.start.column-1)
                end = buffer.primary_view().text_point(row=span.end.line-1, col=span.end.column-1)
                region = sublime.Region(start, end)
                phantoms.append(sublime.Phantom(region=region, content="<body><style>body { background-color: color(yellow alpha(0.25)); padding: 0.5em; }</style>Missing proof</body>", layout=sublime.PhantomLayout.BELOW))

        # print("|good| = {}".format(len(good_ranges)))
        # print("|bad| = {}".format(len(bad_ranges)))

        for view in buffer.views():
            view.add_regions("TLAPM_GOOD", good_ranges, scope="region.greenish", flags=sublime.DRAW_NO_OUTLINE|sublime.NO_UNDO)
            view.add_regions("TLAPM_BAD", bad_ranges, scope="region.redish", flags=sublime.DRAW_NO_OUTLINE|sublime.NO_UNDO)
            view.set_status(TLAPM_STATUS_KEY, "")
            self._find_phantom_set_on_main_thread(view).update(phantoms)

    def _clear_proof_state_on_main_thread(self, buffer):
        for view in buffer.views():
            view.add_regions("TLAPM_GOOD", [])
            view.add_regions("TLAPM_BAD", [])
            view.set_status(TLAPM_STATUS_KEY, "")
            self._find_phantom_set_on_main_thread(view).update([])


def _mark_dirty(buf: sublime.Buffer):
    if view := buf.primary_view():
        if syntax := view.syntax():
            if syntax.path.endswith("/tlaplus.sublime-syntax"):
                if file := buf.file_name():
                    id = buf.id()
                    with dirty_buffers_monitor:
                        dirty_buffers[id] = (buf, file)
                        dirty_buffers_monitor.notify()


class TLAPMEventListener(sublime_plugin.EventListener):

    def on_init(self, views):
        for view in views:
            _mark_dirty(view.buffer())

    def on_load(self, view):
        _mark_dirty(view.buffer())

    def on_post_save(self, view):
        _mark_dirty(view.buffer())


# class TLAPMTextChangeListener(sublime_plugin.TextChangeListener):

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._running = True
#         self._monitor = threading.Condition()
#         self._dirty = None
#         self._proc = None
#         self._thread = threading.Thread(target=self._bg_job)
#         self._thread.start()
#         self._file = None

#     @classmethod
#     def is_applicable(cls, buffer):
#         syntax = buffer.primary_view().syntax()
#         return syntax is not None and syntax.path.endswith("/tlaplus.sublime-syntax")
#         return buffer.primary_view().settings().get("syntax", "").endswith("/tlaplus.sublime-syntax")

#     def attach(self, buf: sublime.Buffer):
#         super().attach(buf)
#         self.mark_dirty()

#     def detach(self):
#         self.stop()
#         super().detach()

#     def on_text_changed(self, changes):
#         print("{}: {}".format(self, changes))
#         self.mark_dirty()
