(function($){
    $(function () {
        // Keep the most recent market close value in memory
        var currentCloseHHMM = '16:00';

        function getTimeInput() {
            var $time = $('#id_dt_1');
            if ($time.length) return $time;
            var $single = $('#id_dt');
            if ($single.length) return $single;
            return $();
        }

        function setTimeInput(hhmm) {
            // Only set when the explicit "Market Close" link is clicked
            var $time = $('#id_dt_1');
            if ($time.length) {
                $time.val(hhmm).trigger('change');
                return;
            }
            var $single = $('#id_dt');
            if ($single.length) {
                var cur = $single.val() || '';
                var m = cur.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?$/);
                if (m) {
                    $single.val(m[1] + ' ' + hhmm).trigger('change');
                } else {
                    $single.val(hhmm).trigger('change');
                }
            }
        }

        // Create or update the single inline "Market Close" link next to the time field
        function ensureMarketCloseLink(closeHHMM, visible) {
            var $timeInput = getTimeInput();
            if (!$timeInput.length) return;

            // Try to place inside the existing Django shortcuts span next to the time input
            var $shortcuts = $timeInput.nextAll('.datetimeshortcuts').first();
            var linkId = 'market_close_shortcut';

            function createLink() {
                var $link = $('<a/>', {
                    id: linkId,
                    href: '#',
                    text: 'Market Close',
                    click: function(e){
                        e.preventDefault();
                        setTimeInput(closeHHMM);
                    }
                });
                return $link;
            }

            if ($shortcuts.length) {
                var $existing = $shortcuts.find('#' + linkId);
                if (!$existing.length) {
                    // Clear other shortcuts if any; we only want our link per requirements
                    $shortcuts.empty();
                    $shortcuts.append(createLink());
                }
                // Update handler and visibility/text every time
                $existing = $shortcuts.find('#' + linkId);
                $existing.off('click').on('click', function(e){
                    e.preventDefault();
                    setTimeInput(closeHHMM);
                });
                $existing.text('Market Close');
                if (visible) {
                    $existing.show();
                    $shortcuts.show();
                } else {
                    $existing.hide();
                    // Keep the container but hide it if it becomes empty/hidden
                    $shortcuts.hide();
                }
            } else {
                // No Django shortcuts span found; create our own right after the input
                var $span = $('<span/>', { 'class': 'datetimeshortcuts' });
                $span.append(createLink());
                $timeInput.after(' ').after($span);
                // Apply initial visibility
                if (!visible) {
                    $span.hide();
                }
            }
        }

        function fetchAndUpdateMarketCloseLink(tickerId) {
            if (!tickerId) {
                // Hide the link entirely when no ticker is selected
                ensureMarketCloseLink(currentCloseHHMM, false);
                return;
            }
            $.get('/markets/api/t_close/', { ticker_id: tickerId })
                .done(function (data) {
                    var hhmm = (data && data.t_close) ? data.t_close : '16:00';
                    currentCloseHHMM = hhmm;
                    // Show/update the single link
                    ensureMarketCloseLink(hhmm, true);
                })
                .fail(function () {
                    // On failure, still show link with default
                    currentCloseHHMM = '16:00';
                    ensureMarketCloseLink('16:00', true);
                });
        }

        function bindTickerEvents() {
            var $ticker = $('#id_ticker');
            if ($ticker.length) {
                // Initialize immediately with current value but do NOT change time automatically
                fetchAndUpdateMarketCloseLink($ticker.val());
                // Bind to multiple possible events (plain select, select2, text input)
                $ticker.on('change select2:select input', function () {
                    fetchAndUpdateMarketCloseLink($(this).val());
                });
                return true;
            }
            return false;
        }

        // We explicitly do NOT inject anything into the time popup nor modify DateTimeShortcuts.
        // Only a single inline "Market Close" link is shown when a ticker is selected.

        if (!bindTickerEvents()) {
            // If the field isn't present yet (e.g., autocomplete widget initializes late), retry briefly
            var attempts = 0;
            var timer = setInterval(function(){
                attempts += 1;
                if (bindTickerEvents() || attempts > 20) {
                    clearInterval(timer);
                    // If we failed to bind, ensure any existing shortcut area is hidden
                    if (attempts > 20) ensureMarketCloseLink(currentCloseHHMM, false);
                }
            }, 150);
        }
    });
})( (window.django && window.django.jQuery) || window.jQuery );
