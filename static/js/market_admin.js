// Very simple hardcoded helpers for Market.t_close in Market admin.
// Avoid DateTimeShortcuts entirely so non-hour times like 16:15 work.
(function($){
    $(function(){
        var $time = $('#id_t_close');
        if (!$time.length) return;

        // Create a shortcuts span right after the input (replace existing if present)
        var $shortcuts = $time.nextAll('.datetimeshortcuts').first();
        if (!$shortcuts.length) {
            $shortcuts = $('<span/>', { 'class': 'datetimeshortcuts' });
            $time.after(' ').after($shortcuts);
        } else {
            $shortcuts.empty();
        }

        function makeLink(id, label, value){
            var $a = $('<a/>', { id: id, href: '#', text: label });
            $a.on('click', function(e){
                e.preventDefault();
                $time.val(value).trigger('change');
            });
            return $a;
        }

        // Hardcoded options per request
        $shortcuts
            .append(makeLink('mc_1600', 'Equities 4:00', '16:00'))
            .append(' | ')
            .append(makeLink('mc_1615', 'Futures 4:15', '16:15'));
    });
})( (window.django && window.django.jQuery) || window.jQuery );