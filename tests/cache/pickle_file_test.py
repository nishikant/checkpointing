from checkpointing import defaults
import pathlib
import shutil
from checkpointing.cache.pickle_file import PickleFileCache, CheckpointNotExist
from nose import with_setup
import pickle

tmpdir = pathlib.Path(".checkpointing-unit-test-tmp")


def teardown_module():
    rmdir_func()


def rmdir_func():
    if tmpdir.exists():
        shutil.rmtree(tmpdir)

@with_setup(setup=rmdir_func)
def test_cache_creates_dir_automatically():

    assert not tmpdir.exists()
    PickleFileCache(tmpdir)
    assert tmpdir.exists()

def test_cache_saves_result_to_pickle():

    value = [1,2,3]
    PickleFileCache(tmpdir).save("0", value)

    filepath = tmpdir.joinpath("0.pickle")
    assert filepath.exists()

    with open(filepath, "rb") as f:
        assert pickle.load(f) == value

def test_cache_retrieves_result():
    pass
