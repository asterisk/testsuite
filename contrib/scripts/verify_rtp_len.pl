#!/usr/bin/perl

use strict;

# This perl program parses an RTP dump file and looks for and verifies the RTP frame length len=xxx

# Check the number of command lines arguments

my $num_args = @ARGV;
if ($num_args ne 2)
{
	print "[VERIFY RTP LEN] needs 2 arguments\n";
	exit(99);
}
else
{
	my $ret=99;
	my $dump_file = $ARGV[0];
	my $len = $ARGV[1];
    if (open(FILE_PTR,$dump_file)) {
		my $count = 0;
		my $line;
		my @lines;
		my $dump_length = 0;

		# Read the dump file into array @lines
		@lines = <FILE_PTR>;
		close FILE_PTR;
		$dump_length = @lines;

		# Process the dump file
		for ($count = 0; $count < $dump_length; $count++) {
			$line = @lines[$count];
			#Check for the payload type
			if ($line =~ /.*len=([0-9]+).*/) {
				if($1 ne $len) {
					$ret = 99;
					last;
				} else {
					$ret=0;
				}
			}
		}
	} else {
		print("Failed to open dump file = $dump_file\n");
		exit(99);
	}
	exit($ret);
}
