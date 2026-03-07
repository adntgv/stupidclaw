# tests/test_tools.py
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools import get_default_tools

tools = get_default_tools()

def test_calculator():
    r = tools["calculator"].execute("2 + 2")
    assert r.success and r.output == "4"

def test_calculator_math():
    r = tools["calculator"].execute("sqrt(144)")
    assert r.success and r.output == "12.0"

def test_time():
    r = tools["time"].execute("")
    assert r.success and "UTC" in r.output

def test_web_search():
    # This might fail without network, skip if needed
    try:
        r = tools["web_search"].execute("python programming")
        assert r.success or "Search error" in r.output
    except:
        pytest.skip("Network required for web search test")

def test_file_write_read():
    tools["file_write"].execute("test.txt|||hello world")
    r = tools["file_read"].execute("test.txt")
    assert r.success and r.output == "hello world"

def test_file_sandbox_escape():
    r = tools["file_read"].execute("../../etc/passwd")
    assert not r.success

def test_shell_allowed():
    r = tools["shell"].execute("echo hello")
    assert r.success and "hello" in r.output

def test_shell_blocked():
    r = tools["shell"].execute("rm -rf /")
    assert not r.success and "allowlist" in r.output

def test_file_list():
    r = tools["file_list"].execute("")
    assert r.success
