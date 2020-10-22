$(document).ready(function() {
    $('.js-relay-btn').click(function(){
        const relayBtnId = $(this).data('relay-btn-id');
        const button = $(this);
        const initialText = button.html();
        button.html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>');
        button.attr('disabled', true);
        $.ajax({
            type: "PUT",
            url: '/on_relay_clicked/' + relayBtnId,
            success: function(){
                button.html(initialText);
                button.attr('disabled', false);
                button.addClass('btn-success').removeClass('btn-light');
                setTimeout(function(){ button.addClass('btn-light').removeClass('btn-success'); }, 2000);
            },
            error: function(){
                button.html(initialText);
                button.attr('disabled', false);
                button.addClass('btn-danger').removeClass('btn-light');
                setTimeout(function(){ button.addClass('btn-light').removeClass('btn-danger'); }, 2000);
                // TODO display error message
            }
        });
    });

    $('#userEditModal').on('show.bs.modal', function (event) {
        const button = $(event.relatedTarget);
        $('#inputUserName').val(button.data('user-name'));
        $('#inputUserId').val(button.data('user-id'));
    });
});
