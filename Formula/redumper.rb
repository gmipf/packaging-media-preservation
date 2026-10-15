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
  url "https://github.com/superg/redumper/archive/refs/tags/b764.tar.gz"
  sha256 "0a039ed32779a318ce4c4b5e40a451b5a9ddc09b5d4e6d36698a1397358641d5"
  license "GPL-3.0-only"

  depends_on :macos

  resource "binary" do
    on_arm do
      url "https://github.com/superg/redumper/releases/download/b764/redumper-b764-macos-arm64.zip"
      sha256 "a0954615846530fd87eca59d261fc827fc86bbd0bec45364a7582b60eb04c829"
    end
    on_intel do
      url "https://github.com/superg/redumper/releases/download/b764/redumper-b764-macos-x64.zip"
      sha256 "9ccdb496b1428a51f4d2f80262db82aa83c81da25ab79a452713b12491ecb3d8"
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
