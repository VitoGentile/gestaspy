# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

assets = [os.path.join(dirpath, file) for (dirpath, dirnames, filenames) in os.walk('assets') for file in filenames]
a = Analysis(['cli.py'],
             pathex=['C:\\Users\\vitog\\Desktop\\gestaspy'],
             binaries=[],
             datas=[(a, os.path.dirname(a)) for a in assets if not(a.endswith(".ico"))],
             hiddenimports=[
                'numpy.distutils',
                'numpy.distutils.ccompiler',
                'distutils.version',
                'numpy.distutils.log',
                'numpy.distutils.misc_util',
                'numpy.distutils.exec_command',
                'numpy.distutils.unixccompiler',
                'distutils.unixccompiler',
                'numpy.distutils.npy_pkg_config',
                'distutils.dist',
                'numpy.distutils.command',
                'numpy.distutils.command.config',
                'distutils.command.config',
                'numpy.distutils.mingw32ccompiler',
                'distutils.cygwinccompiler',
                'distutils.msvccompiler',
                'numpy.distutils.command.autodist',
                'numpy.distutils._shell_utils'
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='gestaspy',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon=os.path.join('assets', 'punch.ico'))
