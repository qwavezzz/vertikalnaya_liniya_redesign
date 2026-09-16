/* OT Document JAVASCRIPT */
jQuery.noConflict();
jQuery(document).ready(function($) {
	$('a.ot_scrollable').bind('click', function(e) {
		e.preventDefault();
		$('html,body').animate({scrollTop: $(this.hash).offset().top});                                                         
	});
});