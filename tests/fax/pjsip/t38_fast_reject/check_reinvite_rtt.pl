#!/usr/bin/perl
use strict;
use Text::CSV;
use Data::Dumper;

my $filename = $ARGV[0];
open(my $fh, '<:utf8', $filename)
    or die "Can't open $filename: $!";

my $csv = Text::CSV->new({sep_char => ';'})
    or die "Text::CSV error: " . Text::CSV->error_diag;

my $header = <$fh>; 
# define column names    
$csv->parse($header);
$csv->column_names([$csv->fields]);

my $ret = 0;
# parse the rest
while (my $row = $csv->getline_hr($fh)) {
    if (!defined  $row->{'ResponseTimereinvite(P)'} ) {
	    print "column not found! make sure scenario is correct!\n";
	    $ret = -1;
	    last;
    }
 
    my $pkey = $row->{'ResponseTimereinvite(P)'};
    my ($hour, $minute, $second, $msec) = split(/:/, $pkey);
    $minute += $hour*60;
    $second += $minute*60;
    $msec += $second * 1000;
    
    if ($msec > 500) {
	    print "Slow 488 Rejection detected ($msec)!\n";
	    $ret = -2;
	    last;
    }
}

$csv->eof or $csv->error_diag;
close $fh;

exit $ret;
