#!/usr/bin/python2

import sys, os, subprocess, string, re, json

# Remove when we refactor unit-tests and allow to pass custom options
os.environ["CLAZY_EXTRA_OPTIONS"] = "qstring-arg-fillChar-overloads"

class Test:
    def __init__(self):
        self.filename = ""
        self.minimum_qt_version = 500
        self.minimum_clang_version = 360
        self.compare_everything = False

    def isScript(self):
        return self.filename.endswith(".sh")

class Check:
    def __init__(self, name):
        self.name = name
        self.link = False # If true we also call the linker
        self.minimum_qt_version = 500 # Qt 5.0.0
        self.minimum_clang_version = 360 # clang 3.6.0
        self.tests = []
#-------------------------------------------------------------------------------
# utility functions #1

def get_command_output(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    if p.wait() != 0:
        return ""
    return p.communicate()[0];

def load_json(check_name):
    check = Check(check_name)
    filename = check_name + "/config.json"
    if not os.path.exists(filename):
        return check

    f = open(filename, 'r')
    contents = f.read()
    f.close()
    decoded = json.loads(contents)

    if 'link' in decoded:
        check.link = decoded['link']

    if 'minimum_qt_version' in decoded:
        check.minimum_qt_version = decoded['minimum_qt_version']

    if 'minimum_clang_version' in decoded:
        check.minimum_clang_version = decoded['minimum_clang_version']

    if 'tests' in decoded:
        for t in decoded['tests']:
            test = Test()
            test.filename = t['filename']
            if 'minimum_qt_version' in t:
                test.minimum_qt_version = t['minimum_qt_version']
            if 'minimum_clang_version' in t:
                test.minimum_qt_version = t['minimum_clang_version']
            if 'compare_everything' in t:
                test.compare_everything = t['compare_everything']
            check.tests.append(test)

    return check

#-------------------------------------------------------------------------------
# Detect Qt include path
# We try in order:
#   QT_SELECT=5 qmake
#   qmake-qt5
#   qmake
QMAKE_HEADERS = ""
qmakes = ["QT_SELECT=5 qmake", "qmake-qt5", "qmake"]
for qmake in qmakes:
    QMAKE_VERSION = get_command_output(qmake + " -query QT_VERSION")
    if QMAKE_VERSION.startswith("5."):
        QMAKE_HEADERS = get_command_output(qmake + " -query QT_INSTALL_HEADERS").strip()
        break

QMAKE_INT_VERSION = int(QMAKE_VERSION.replace(".", ""))

if not QMAKE_HEADERS:
    # Change here if can't find with qmake
    QMAKE_HEADERS = "/usr/include/qt/"

QT_FLAGS = "-isystem " + QMAKE_HEADERS + " -fPIC"

#-------------------------------------------------------------------------------
# Get clang version
version = get_command_output('clang --version')

match = re.search('clang version (.*?)[ -]', version)
version = match.group(1)

CLANG_VERSION = int(version.replace('.', ''))

#-------------------------------------------------------------------------------
# Global variables

_compiler_comand = "clang++ -std=c++11 -Wno-unused-value -Qunused-arguments -Xclang -load -Xclang ClangLazy.so -Xclang -add-plugin -Xclang clang-lazy -Xclang -plugin-arg-clang-lazy -Xclang no-inplace-fixits -Xclang -plugin-arg-clang-lazy -Xclang enable-all-fixits " + QT_FLAGS
_link_flags = "-lQt5Core -lQt5Gui -lQt5Widgets"
_dump_ast_command = "clang++ -std=c++11 -fsyntax-only -Xclang -ast-dump -fno-color-diagnostics -c *.cpp " + QT_FLAGS
_help_command = "echo | clang++ -Xclang -load -Xclang ClangLazy.so -Xclang -add-plugin -Xclang clang-lazy -Xclang -plugin-arg-clang-lazy -Xclang help -c -xc -"
_dump_ast = "--dump-ast" in sys.argv
_verbose = "--verbose" in sys.argv
_help = "--help" in sys.argv
_only_checks = "--only-checks" in sys.argv # If set, the tests for the compiler itself aren't run
#-------------------------------------------------------------------------------
# utility functions #2

def run_command(cmd):
    if os.system(cmd) != 0:
        return False
    return True

def print_usage():
    print "Usage for " + sys.argv[0].strip("./") + ":\n"
    print "    " + sys.argv[0] + " [--help] [--dump-ast] [--only-checks] [check1,check2,check3]"
    print
    print "    Without any check supplied, all checks will be run."
    print "    --dump-ast is provided for debugging purposes.\n"
    print "Help for clang plugin:"
    print
    run_command(_help_command)

def files_are_equal(file1, file2):
    try:
        f = open(file1, 'r')
        lines1 = f.readlines()
        f.close()

        f = open(file2, 'r')
        lines2 = f.readlines()
        f.close()

        return lines1 == lines2
    except:
        return False

def get_check_names():
    return filter(lambda entry: os.path.isdir(entry), os.listdir("."))

# Returns all files with .cpp_fixed extension. These were rewritten by clang.
def get_fixed_files():
    return filter(lambda entry: entry.endswith('.cpp_fixed.cpp'), os.listdir("."))

def print_differences(file1, file2):
    return run_command("diff -Naur {} {}".format(file1, file2))

def extract_word(word, in_file, out_file):
    in_f = open(in_file, 'r')
    out_f = open(out_file, 'w')
    for line in in_f:
        if word in line:
            out_f.write(line)
    in_f.close()
    out_f.close()

def cleanup_fixed_files():
    fixed_files = get_fixed_files()
    for fixed_file in fixed_files:
        os.remove(fixed_file)


def run_check_unit_tests(check):
    cmd = ""
    if check.link:
        cmd += _compiler_comand + " " + _link_flags
    else:
        cmd += _compiler_comand + " -c "

    hasSingleTest = len(check.tests) == 1
    for test in check.tests:
        if QMAKE_INT_VERSION < test.minimum_qt_version or CLANG_VERSION < test.minimum_clang_version:
            continue

        output_file = test.filename + ".out"
        result_file = test.filename + ".result"
        expected_file = test.filename + ".expected"

        if test.isScript():
            clazy_cmd = "./" + test.filename
        else:
            clazy_cmd = cmd + " -Xclang -plugin-arg-clang-lazy -Xclang " + check.name + " " + test.filename

        if test.compare_everything:
            result_file = output_file

        if _verbose:
            print "Running: " + clazy_cmd

        if not run_command(clazy_cmd + " > " + output_file + " 2> " + output_file):
            print "[FAIL] " + check.name + " (Failed to build test. Check " + check.name + "/" + output_file + " for details)"
            print
            return False

        if not test.compare_everything:
            extract_word("warning:", output_file, result_file)

        printableName = check.name
        if not hasSingleTest:
            printableName += "/" + test.filename

        if files_are_equal(expected_file, result_file):
            print "[OK]   " + printableName
        else:
            print "[FAIL] " + printableName
            if not print_differences(expected_file, result_file):
                return False

    return True

def dump_ast(check):
    run_command(_dump_ast_command + " > dump.ast")
#-------------------------------------------------------------------------------
def load_checks(all_check_names):
    checks = []
    for name in all_check_names:
        checks.append(load_json(name))
    return checks
#-------------------------------------------------------------------------------
# main

if _help:
    print_usage()
    sys.exit(0)

args = sys.argv[1:]

switches = ["--verbose", "--dump-ast", "--help", "--only-checks"]

if _dump_ast:
    del(args[args.index("--dump-ast")])

all_check_names = get_check_names()
all_checks = load_checks(all_check_names)
requested_check_names = filter(lambda x: x not in switches, args)
requested_check_names = map(lambda x: x.strip("/"), requested_check_names)

for check_name in requested_check_names:
    if check_name not in all_check_names:
        print "Unknown check: " + check_name
        print
        sys.exit(-1)

if not requested_check_names:
    requested_check_names = all_check_names

requested_checks = filter(lambda check: check.name in requested_check_names, all_checks)
requested_checks = filter(lambda check: check.minimum_qt_version <= QMAKE_INT_VERSION, requested_checks)
requested_checks = filter(lambda check: check.minimum_clang_version <= CLANG_VERSION, requested_checks)

for check in requested_checks:
    os.chdir(check.name)
    if _dump_ast:
        dump_ast(check)
    else:
        if not run_check_unit_tests(check):
            exit(-1)

    os.chdir("..")
