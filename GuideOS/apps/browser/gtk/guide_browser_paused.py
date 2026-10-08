"""Inactive release entry: no display owner, toolkit or browser engine is loaded."""


def run(headless=False, runtime_path=None):
    raise RuntimeError('Web browsing is paused for now')


if __name__ == '__main__':
    run()
