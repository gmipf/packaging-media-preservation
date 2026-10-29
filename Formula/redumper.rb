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
  url "https://github.com/superg/redumper/archive/refs/tags/b770.tar.gz"
  sha256 "09aa50d1ca57269e1d94702b80610ffb5086ec32abd14aef51954f5412a1c7c6"
  license "GPL-3.0-only"

  depends_on :macos

  resource "binary" do
    on_arm do
      url "https://github.com/superg/redumper/releases/download/b770/redumper-b770-macos-arm64.zip"
      sha256 "a63bd580fd19dfd6a353f39e403396a47494a8601f81c34b3257dd8040dd4e5f"
    end
    on_intel do
      url "https://github.com/superg/redumper/releases/download/b770/redumper-b770-macos-x64.zip"
      sha256 "c0a56ab2a06aac0705c0cf01062aaa376e3bb9bba9c18af8ed96931bd23551d2"
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
