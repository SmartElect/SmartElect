// From http://legacy.datatables.net/plug-ins/sorting
// "This plug-in will provide numeric sorting for numeric columns which have
// extra formatting, such as thousands separators, currency symbols or any
// other non-numeric data."
jQuery.extend( jQuery.fn.dataTableExt.oSort, {
    "formatted-num-pre": function ( a ) {
        a = (a === "-" || a === "") ? 0 : a.replace( /[^\d\-\.]/g, "" );
        return parseFloat( a );
    },

    "formatted-num-asc": function ( a, b ) {
        return a - b;
    },

    "formatted-num-desc": function ( a, b ) {
        return b - a;
    }
} );

$(document).ready(function() {
    var oLanguage = {};
    if ($("html").attr("lang") === "ar") {
        oLanguage = {
            'sSearch':unescape("%u0628%u062D%u062B"),
            'sZeroRecords':unescape("%u0644%u0627%20%u062A%u0648%u062C%u062F%20%u0645%u0628%u0627%u0631%u0627%u0629"),
            'sLengthMenu':unescape("%u0623%u0638%u0647%u0631%20_MENU_%20%u0625%u062F%u062E%u0627%u0644%u0627%u062A"),
            "oPaginate": {
                'sNext':unescape("%u0644%u0627%u062D%u0642"),
                'sPrevious':unescape("%u0633%u0627%u0628%u0642")
            }
        };
    }

    $('table.js-sortable').dataTable({
        "pagingType": "simple",
        "aaSorting": [[ 1, "asc" ]],
        "aoColumnDefs": [
            // Use the formatted-num sort plugin to sort intcomma-formatted or
            // blank counts of registrations or votes reported by period.
            { "sType": "formatted-num", "aTargets": ["formatted-count"]}
        ],
        "asStripeClasses": ["datatables-odd-rows", "datatables-even-rows"],
        "bPaginate": true,
        "bLengthChange": false,
        "bFilter": true,
        "bSort": true,
        "bInfo": false,
        "bAutoWidth": true,
        "fnInitComplete": function () {
            $('#loading').hide();
            $('table.js-sortable').show();
        },
        "iDisplayLength": 20,
        "oLanguage": oLanguage
    });
});
