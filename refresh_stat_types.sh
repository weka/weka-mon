weka stats list-types -H vweka01 -o category,identifier,unit --no-header --show-internal | awk 'BEGIN{cat="";unit="unit"}{
unit=$3;
if( unit == "" )
    unit="none";
#if( unit == "Microseconds" )
#    unit="microsecs";

if( cat != $1 ) {
    printf("#  %s:\n#    %s: %s\n",$1, $2, unit);
    cat = $1;
} else {
    printf("#    %s: %s\n",$2, unit );
}
}' 
