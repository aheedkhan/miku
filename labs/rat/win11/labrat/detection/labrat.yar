rule labrat_beacon_strings {
    meta:
        description = "Lab research implant labrat v0.5 — WinHTTP beacon strings"
        author = "lab"
        reference = "labs/rat/win11/labrat"
    strings:
        $ua = "LabRat/0.5" ascii
        $checkin = "\"op\":\"checkin\"" ascii
        $result = "\"op\":\"result\"" ascii
        $beacon = "/beacon" ascii
    condition:
        uint16(0) == 0x5A4D and 2 of them
}
