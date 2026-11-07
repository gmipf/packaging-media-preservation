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
  url "https://github.com/superg/redumper/archive/refs/tags/b772.tar.gz"
  sha256 "f600c6bdc302e60cf0405d87d5dadb4aa63fb25f5809f99b4d837c57dd208916"
  license "GPL-3.0-only"

  depends_on :macos

  resource "binary" do
    on_arm do
      url "https://github.com/superg/redumper/releases/download/b772/redumper-b772-macos-arm64.zip"
      sha256 "944f2a0b40900104338431e40df71d36666904e98511c11a6164cc69737f8660"
    end
    on_intel do
      url "https://github.com/superg/redumper/releases/download/b772/redumper-b772-macos-x64.zip"
      sha256 "c7a90d98ec62321a8d8ef0f270f055c8bf8859c8052879a75c57d20cd03b8c1c"
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
