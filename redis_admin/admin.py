from django.contrib import admin
from django.db import models
try:
    from django.conf.urls import patterns
except ImportError:
    from django.conf.urls.defaults import patterns
from django.core.cache import cache
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages


class RedisAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super(RedisAdmin, self).get_urls()

        my_urls = patterns('',
            (r'^$', self.index),
            (r'^(?P<key>.+)/delete/$', self.delete),
            (r'^(?P<key>.+)/$', self.key),
        )
        return my_urls + urls

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def index(self, request):

        if request.method == 'POST' and request.POST.getlist('_selected_action') and \
            request.POST.get('action') == 'delete_selected' and \
            request.POST.get('post') == 'yes':

            cache.delete_many(request.POST.getlist('_selected_action'))
            if not len(cache.get_many(request.POST.getlist('_selected_action'))):
                messages.add_message(request, messages.SUCCESS,
                                    'Successfully deleted %d keys.' %
                                    len(request.POST.getlist('_selected_action')))
            else:
                messages.add_message(request, messages.ERROR,
                                    'Could not delete %d keys.' %
                                    len(request.POST.getlist('_selected_action')))

        elif request.method == 'POST' and request.POST.getlist('_selected_action') and \
            request.POST.get('action') == 'delete_selected':

            return render_to_response('redis_admin/delete_selected_confirmation.html',
                                     {'keys': request.POST.getlist('_selected_action')},
                                     context_instance=RequestContext(request))

        if request.GET.get('q'):
            keys_result = cache.keys('*%s*' % request.GET.get('q'))
        else:
            keys_result = cache.keys('*')

        paginator = Paginator(keys_result, 100)

        page = request.GET.get('p')

        try:
            keys = paginator.page(page)
        except PageNotAnInteger:
            keys = paginator.page(1)
        except EmptyPage:
            keys = paginator.page(paginator.num_pages)

        return render_to_response('redis_admin/index.html', {'keys': keys,
                                  'count': paginator.count, 'page_range': paginator.page_range},
                                   context_instance=RequestContext(request))

    @property
    def cache_client(self):
        if hasattr('raw_client', cache):
            # django-redis package
            return cache.raw_client
        else:
            # django-redis-cache package
            return cache._client

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def key(self, request, key):

        try:
            # not all redis cache supprots this method
            key_type = self.cache_client.type(key)
        except:
            key_type = None

        if key_type == 'none':
            raise Http404

        context = {'key': key, 'type': key_type}

#        if key_type == 'string':
#             context['value'] = self.cache_client.get(key)
        if key_type == 'set':
            context['value'] = str(self.cache_client.smembers(key))
        else:
            context['value'] = self.cache_client.get(key)

        return render_to_response('redis_admin/key.html', context,
                                   context_instance=RequestContext(request))

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def delete(self, request, key):
        if request.method == "POST" and request.POST.get('post') == 'yes':
            cache.delete(key)
            if not cache.get(key):
                messages.add_message(request, messages.SUCCESS, 'The key "%s" was deleted successfully.' % key)
            else:
                messages.add_message(request, messages.ERROR, 'The key "%s" was not deleted successfully.' % key)
            return HttpResponseRedirect('%sredis/manage/' % reverse('admin:index'))
        return render_to_response('redis_admin/delete_confirmation.html',
                                 {'key': key}, context_instance=RequestContext(request))

class Meta:
    app_label = 'redis'
    verbose_name = 'Manage'
    verbose_name_plural = "Manage"

admin.site.register(type('manage', (models.Model,), {'__module__': '', 'Meta': Meta}), RedisAdmin)
