# redumper for macOS: upstream's own release build, repackaged. It ships its own
# libc++ in lib/ and finds it through RPATH @executable_path/../lib, so bin/ and
# lib/ stay together under libexec, and bin/redumper is a script that execs the
# real file (a symlink would hand the loader the wrong @executable_path).
#
# Homebrew allows no per-architecture url in a formula, only a per-architecture
# resource. So the url is the source tarball of the same tag -- it carries the
# LICENSE and README the binary zips lack, and Homebrew installs both -- and
# the binary comes from the resource for this machine.
#
# The build number follows fedora/redumper/redumper.spec: the same watcher bumps
# every lane in one commit.
class Redumper < Formula
  desc "Low-level byte-perfect CD disc dumper"
  homepage "https://github.com/superg/redumper"
  url "https://github.com/superg/redumper/archive/refs/tags/b774.tar.gz"
  sha256 "1e3908e2198fcc5de45cb2ae0135aca9599c316eacd1888964b9ec74985cf66a"
  license "GPL-3.0-only"

  depends_on :macos

  resource "binary" do
    on_arm do
      url "https://github.com/superg/redumper/releases/download/b774/redumper-b774-macos-arm64.zip"
      sha256 "81bcf23da1ec438a55915228a9e253dbd05c1551c74792704256742f24db7e2b"
    end
    on_intel do
      url "https://github.com/superg/redumper/releases/download/b774/redumper-b774-macos-x64.zip"
      sha256 "3ca564718589b590bb1285358e36206e983f4c881b3bdf418593c0b7b5a5f533"
    end
  end

  def install
    resource("binary").stage do
      libexec.install "bin", "lib"
    end
    bin.write_exec_script libexec/"bin/redumper"
  end

  def caveats
    <<~EOS
      Name the drive by its BSD name, as `diskutil list` shows it:
        redumper disc --drive=disk4
      (not /dev/disk4). No root is needed. macOS refuses drive access to a
      program working inside Desktop, Documents or Downloads, so dump into
      another folder.
    EOS
  end

  test do
    assert_match "build: b#{version}", shell_output("#{bin}/redumper --version")
  end
end
