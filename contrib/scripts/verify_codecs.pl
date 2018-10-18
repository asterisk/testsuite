#!/usr/bin/perl

use strict;

# This perl program parses an RTP dump file and looks for the codec
# names provided on the command line in the RTM DUMP file, if none 
# of the pref_codecs are found in RTP dump file, it exits with a status
# code of 99 otherwise it will exit with a status code of 0

# This perl program expects minium of two arguments on command line,
# First argument is the name of RTP dump, second argument and so on
# are the codec names to be searched in RTP dump file

# Check the number of command lines arguments

my $num_args = @ARGV;
if ($num_args < 2)
{
	print "[VERIFY CODECS]Insufficient arguments\n";
	exit(99);
}
else
{
	my $FILE_PTR;
	my $bad_codec = 0;
	my $lock_codec = 0;
	my @pref_codecs = @ARGV[1..$num_args];
	my $dump_file = $ARGV[0];
        if (open(FILE_PTR,$dump_file))
	{
		my $count=0;
		my $line;
		my @lines;
		my $dump_length=0;

		# Read the dump file into arrat @lines 
		@lines = <FILE_PTR>;
		close FILE_PTR;
		$dump_length = @lines;

		# Process the dump file 
		for ($count=0;$count<$dump_length;$count++)
		{
			$line = @lines[$count];
			#Check for the payload type
			if ($line =~ /.*pt=([0-9]+).*/)	
			{
				my $match=0;
				#Check the payload type matched any of the expected
				#payload types
				if($lock_codec == 0)
				{
					#system settled down on desired codec
					#make sure it keeps on that codec
					if ($pref_codecs[0] eq $1)
					{
						$lock_codec=1;
						$match=1;
					}
					else
					{
						foreach my $pref_codec (@pref_codecs)
						{
							if ($pref_codec eq $1)
							{
								$match=1;
							}
						}
					}
				}
				elsif ($pref_codecs[0] eq $1)
				{
					$match=1;
				}

				if ($match == 0)
				{
					$bad_codec = 1;
					last;
				}

					
			}
			
		}


		if ($bad_codec eq 1)
		{
			print "[VERIFY_CODECS] Unsupported codecs in dump file [$dump_file]\n";
			exit(99);
		}
		elsif($lock_codec == 0)
		{
			print "[VERIFY_CODECS] Call never switched to preferred codec [$dump_file]\n";
			exit(99);
		}
		else
		{
			exit(0);
		}
	}
	else
	{
		print "[VERIFY_CODECS] Unable to open the dump file [$dump_file]\n";
		exit(99);
	}

}
