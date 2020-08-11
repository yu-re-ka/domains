from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import Http404, HttpResponseBadRequest, HttpResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import django_keycloak_auth.clients
import ipaddress
import grpc
import idna
import jwt
import json
import datetime
from concurrent.futures import ThreadPoolExecutor
from .. import models, apps, forms, zone_info, tasks
from . import gchat_bot


def index(request):
    form = forms.DomainSearchForm()
    tlds = list(map(lambda z: z[0], sorted(zone_info.ZONES, key=lambda z: z[0])))

    return render(request, "domains/index.html", {
        "registration_enabled": settings.REGISTRATION_ENABLED,
        "domain_form": form,
        "tlds": json.dumps(tlds)
    })


def domain_prices(request):
    zones = list(map(lambda z: {
        "zone": z[0],
        "currency": z[1].pricing.currency,
        "registration": z[1].pricing.representative_registration(),
        "renewal": z[1].pricing.representative_renewal(),
        "restore": z[1].pricing.representative_restore(),
        "transfer": z[1].pricing.representative_transfer(),
    }, sorted(zone_info.ZONES, key=lambda z: z[0])))

    return render(request, "domains/domain_prices.html", {
        "domains": zones
    })


def domain_price_query(request):
    if request.method == "POST":
        form = forms.DomainSearchForm(request.POST)
        form.helper.form_action = request.get_full_path()
        if form.is_valid():
            try:
                domain_idna = idna.encode(form.cleaned_data['domain'], uts46=True).decode()
            except idna.IDNAError as e:
                form.add_error('domain', f"Invalid Unicode: {e}")
            else:
                zone, sld = zone_info.get_domain_info(domain_idna)
                if zone:
                    try:
                        data = zone.pricing.fees(sld)
                        return render(request, "domains/domain_price_query.html", {
                            "domain_form": form,
                            "domain_data": data
                        })
                    except grpc.RpcError as rpc_error:
                        return render(request, "domains/domain_price_query.html", {
                            "error": rpc_error.details(),
                            "domain_form": form
                        })
                else:
                    form.add_error('domain', "Unsupported or invalid domain")

    else:
        form = forms.DomainSearchForm()
        form.helper.form_action = request.get_full_path()

    return render(request, "domains/domain_price_query.html", {
        "domain_form": form
    })


@login_required
def domains(request):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domains = models.DomainRegistration.get_object_list(access_token)
    registration_orders = models.DomainRegistrationOrder.get_object_list(access_token)
    transfer_orders = models.DomainTransferOrder.get_object_list(access_token)
    renew_orders = models.DomainRenewOrder.get_object_list(access_token)
    restore_orders = models.DomainRestoreOrder.get_object_list(access_token)
    error = None

    active_domains = []
    deleted_domains = []

    def get_domain(d):
        if d.deleted:
            deleted_domains.append(d)
        else:
            try:
                domain_data = apps.epp_client.get_domain(d.domain)
                if apps.epp_api.rgp_pb2.RedemptionPeriod in domain_data.rgp_state:
                    d.deleted = True
                    d.save()
                    deleted_domains.append(d)
                else:
                    active_domains.append({
                        "id": d.id,
                        "obj": d,
                        "domain": domain_data
                    })
            except grpc.RpcError as rpc_error:
                active_domains.append({
                    "id": d.id,
                    "obj": d,
                    "error": rpc_error.details()
                })

    with ThreadPoolExecutor() as executor:
        executor.map(get_domain, user_domains)

    return render(request, "domains/domains.html", {
        "domains": active_domains,
        "deleted_domains": deleted_domains,
        "registration_orders": registration_orders,
        "transfer_orders": transfer_orders,
        "renew_orders": renew_orders,
        "restore_orders": restore_orders,
        "error": error,
        "registration_enabled": settings.REGISTRATION_ENABLED
    })


@login_required
def domain(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_info = zone_info.get_domain_info(user_domain.domain)[0]

    error = None
    domain_data = None
    registrant = None
    admin = None
    billing = None
    tech = None
    is_hexdns = False
    host_objs = []

    registrant_form = forms.DomainContactForm(
        user=request.user,
        contact_type='registrant',
        domain_id=domain_id,
    )
    registrant_form.fields['contact'].required = True
    admin_contact_form = forms.DomainContactForm(
        user=request.user,
        contact_type='admin',
        domain_id=domain_id,
    )
    billing_contact_form = forms.DomainContactForm(
        user=request.user,
        contact_type='billing',
        domain_id=domain_id,
    )
    tech_contact_form = forms.DomainContactForm(
        user=request.user,
        contact_type='tech',
        domain_id=domain_id,
    )
    new_host_form = forms.HostSearchForm(
        domain_name=user_domain.domain
    )
    host_object_form_set = forms.DomainHostObjectFormSet(
        domain_id=domain_id
    )
    host_addr_form = forms.DomainHostAddrForm(
        domain_id=domain_id
    )
    ds_form = forms.DomainDSDataForm(
        domain_id=domain_id
    )
    dnskey_form = forms.DomainDNSKeyDataForm(
        domain_id=domain_id
    )

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)

        if apps.epp_api.rgp_pb2.RedemptionPeriod in domain_data.rgp_state:
            user_domain.deleted = True
            user_domain.save()
            return redirect('domains')

        if request.method == "POST" and request.POST.get("type") == "host_search":
            new_host_form = forms.HostSearchForm(
                request.POST,
                domain_name=user_domain.domain
            )
            if new_host_form.is_valid():
                try:
                    host_idna = idna.encode(new_host_form.cleaned_data['host'], uts46=True).decode()
                except idna.IDNAError as e:
                    new_host_form.add_error('host', f"Invalid Unicode: {e}")
                else:
                    host = f"{host_idna}.{domain_data.name}"
                    try:
                        available, reason = apps.epp_client.check_host(host, domain_data.registry_name)
                    except grpc.RpcError as rpc_error:
                        error = rpc_error.details()
                    else:
                        if not available:
                            if not reason:
                                new_host_form.add_error('host', "Host name unavailable")
                            else:
                                new_host_form.add_error('host', f"Host name unavailable: {reason}")
                        else:
                            return redirect('host_create', host)

        if domain_info.registrant_supported:
            registrant = models.Contact.get_contact(domain_data.registrant, domain_data.registry_name, request.user)
            registrant_form.set_cur_id(cur_id=domain_data.registrant, registry_id=domain_data.registry_name)
        else:
            registrant = user_domain.registrant_contact
            registrant_form.fields['contact'].value = user_domain.registrant_contact.id

        if domain_data.admin:
            admin = models.Contact.get_contact(domain_data.admin.contact_id, domain_data.registry_name, request.user)
            admin_contact_form.set_cur_id(cur_id=domain_data.admin.contact_id, registry_id=domain_data.registry_name)
        elif user_domain.admin_contact:
            admin = user_domain.admin_contact
            admin_contact_form.fields['contact'].value = user_domain.admin_contact.id

        if domain_data.billing:
            billing = models.Contact.get_contact(domain_data.billing.contact_id, domain_data.registry_name, request.user)
            billing_contact_form.set_cur_id(cur_id=domain_data.billing.contact_id, registry_id=domain_data.registry_name)
        elif user_domain.billing_contact:
            billing = user_domain.billing_contact
            billing_contact_form.fields['contact'].value = user_domain.billing_contact.id

        if domain_data.tech:
            tech = models.Contact.get_contact(domain_data.tech.contact_id, domain_data.registry_name, request.user)
            tech_contact_form.set_cur_id(cur_id=domain_data.tech.contact_id, registry_id=domain_data.registry_name)
        elif user_domain.admin_contact:
            tech = user_domain.tech_contact
            tech_contact_form.fields['contact'].value = user_domain.tech_contact.id

        admin_contact_form.fields['contact'].required = domain_info.admin_required
        billing_contact_form.fields['contact'].required = domain_info.billing_required
        tech_contact_form.fields['contact'].required = domain_info.tech_required

        host_objs = list(map(lambda h: models.NameServer.get_name_server(
            h,
            domain_data.registry_name,
            request.user
        ), domain_data.hosts))

        if all(
                any(
                    (hns == ns.host_obj.lower() if ns.host_obj else hns == ns.host_name.lower())
                    for ns in domain_data.name_servers
                )
                for hns in ("ns1.as207960.net", "ns2.as207960.net")
        ):
            is_hexdns = True

    except grpc.RpcError as rpc_error:
        return render(request, "domains/error.html", {
            "error": rpc_error.details(),
            "back_url": referrer
        })

    return render(request, "domains/domain.html", {
        "domain_id": domain_id,
        "domain_info": domain_info,
        "domain_obj": user_domain,
        "domain": domain_data,
        "error": error,
        "registrant": registrant,
        "admin": admin,
        "billing": billing,
        "tech": tech,
        "hosts": host_objs,
        "registrant_form": registrant_form,
        "admin_contact_form": admin_contact_form,
        "billing_contact_form": billing_contact_form,
        "tech_contact_form": tech_contact_form,
        "new_host_form": new_host_form,
        "host_object_form_set": host_object_form_set,
        "host_addr_form": host_addr_form,
        "ds_form": ds_form,
        "dnskey_form": dnskey_form,
        "registration_enabled": settings.REGISTRATION_ENABLED,
        "is_hexdns": is_hexdns
    })


@login_required
@require_POST
def update_domain_contact(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_info = zone_info.get_domain_info(user_domain.domain)[0]

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    form = forms.DomainContactForm(
        request.POST,
        user=request.user,
        contact_type=None,
        domain_id=user_domain.id,
    )

    contact_type = request.POST.get("type")

    if contact_type == 'admin':
        form.fields['contact'].required = domain_info.admin_required
    elif contact_type == 'billing':
        form.fields['contact'].required = domain_info.billing_required
    elif contact_type == 'tech':
        form.fields['contact'].required = domain_info.tech_required

    if form.is_valid():
        contact_type = form.cleaned_data['type']
        try:
            contact = form.cleaned_data['contact']
            if contact_type != "registrant":
                if contact_type == 'admin':
                    user_domain.admin_contact = contact
                    if domain_info.admin_supported:
                        if contact:
                            contact_id = contact.get_registry_id(domain_data.registry_name)
                            domain_data.set_contact(contact_type, contact_id.registry_contact_id)
                        else:
                            domain_data.set_contact(contact_type, None)
                elif contact_type == 'tech':
                    user_domain.tech_contact = contact
                    if domain_info.tech_supported:
                        if contact:
                            contact_id = contact.get_registry_id(domain_data.registry_name)
                            domain_data.set_contact(contact_type, contact_id.registry_contact_id)
                        else:
                            domain_data.set_contact(contact_type, None)
                elif contact_type == 'billing':
                    user_domain.billing_contact = contact
                    if domain_info.billing_supported:
                        if contact:
                            contact_id = contact.get_registry_id(domain_data.registry_name)
                            domain_data.set_contact(contact_type, contact_id.registry_contact_id)
                        else:
                            domain_data.set_contact(contact_type, None)

                user_domain.save()
            elif domain_info.registrant_change_supported:
                if domain_info.registrant_supported:
                    contact_id = contact.get_registry_id(domain_data.registry_name)
                    domain_data.set_registrant(contact_id.registry_contact_id)

                user_domain.registrant_contact = contact
                user_domain.save()
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def domain_block_transfer(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_info = zone_info.get_domain_info(user_domain.domain)[0]

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    if domain_info.transfer_lock_supported:
        try:
            domain_data.add_states([apps.epp_api.DomainStatus(status=3)])
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def domain_del_block_transfer(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_info = zone_info.get_domain_info(user_domain.domain)[0]

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    if domain_info.transfer_lock_supported:
        try:
            domain_data.del_states([apps.epp_api.DomainStatus(status=3)])
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
def domain_regen_transfer_code(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    new_auth_info = models.make_secret()

    try:
        domain_data.set_auth_info(new_auth_info)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    user_domain.auth_info = new_auth_info
    user_domain.save()

    return redirect(referrer)


@login_required
@require_POST
def add_domain_host_obj(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    form_set = forms.DomainHostObjectFormSet(
        request.POST,
        domain_id=user_domain.id,
    )
    if form_set.is_valid():
        hosts = []

        for form in form_set.forms:
            host_obj = form.cleaned_data.get('host')
            if host_obj:
                try:
                    host_idna = idna.encode(host_obj, uts46=True).decode()
                    hosts.append(host_idna)
                except idna.IDNAError:
                    pass

        for host_obj in hosts:
            try:
                host_available, _ = apps.epp_client.check_host(host_obj, domain_data.registry_name)
            except grpc.RpcError as rpc_error:
                error = rpc_error.details()
                return render(request, "domains/error.html", {
                    "error": error,
                    "back_url": referrer
                })

            if host_available:
                try:
                    apps.epp_client.create_host(host_obj, [], domain_data.registry_name)
                except grpc.RpcError as rpc_error:
                    error = rpc_error.details()
                    return render(request, "domains/error.html", {
                        "error": error,
                        "back_url": referrer
                    })

        try:
            domain_data.add_host_objs(hosts)
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def add_domain_host_addr(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    form = forms.DomainHostAddrForm(
        request.POST,
        domain_id=user_domain.id
    )
    if form.is_valid():
        host_name = form.cleaned_data['host']
        host_addr = form.cleaned_data['address']
        if host_addr:
            address = ipaddress.ip_address(host_addr)
            ip_type = apps.epp_api.common_pb2.IPAddress.IPVersion.UNKNOWN
            if address.version == 4:
                ip_type = apps.epp_api.common_pb2.IPAddress.IPVersion.IPv4
            elif address.version == 6:
                ip_type = apps.epp_api.common_pb2.IPAddress.IPVersion.IPv6
            addrs = [apps.epp_qapi.IPAddress(
                address=address.compressed,
                ip_type=ip_type
            )]
        else:
            addrs = []
        try:
            domain_data.add_host_addrs([(host_name, addrs)])
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def add_domain_ds_data(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    form = forms.DomainDSDataForm(
        request.POST,
        domain_id=domain_id
    )
    if form.is_valid():
        try:
            domain_data.add_ds_data([apps.epp_api.SecDNSDSData(
                key_tag=form.cleaned_data['key_tag'],
                algorithm=form.cleaned_data['algorithm'],
                digest_type=form.cleaned_data['digest_type'],
                digest=form.cleaned_data['digest'],
                key_data=None
            )])
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def delete_domain_ds_data(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    try:
        domain_data.del_ds_data([apps.epp_api.SecDNSDSData(
            key_tag=int(request.POST.get('key_tag')),
            algorithm=int(request.POST.get('algorithm')),
            digest_type=int(request.POST.get('digest_type')),
            digest=request.POST.get('digest'),
            key_data=None
        )])
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    return redirect(referrer)


@login_required
@require_POST
def add_domain_dnskey_data(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    form = forms.DomainDNSKeyDataForm(
        request.POST,
        domain_id=domain_id
    )
    if form.is_valid():
        try:
            domain_data.add_dnskey_data([apps.epp_api.SecDNSKeyData(
                flags=form.cleaned_data['flags'],
                protocol=form.cleaned_data['protocol'],
                algorithm=form.cleaned_data['algorithm'],
                public_key=form.cleaned_data['public_key'],
            )])
        except grpc.RpcError as rpc_error:
            error = rpc_error.details()
            return render(request, "domains/error.html", {
                "error": error,
                "back_url": referrer
            })

    return redirect(referrer)


@login_required
@require_POST
def delete_domain_dnskey_data(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    try:
        domain_data.del_dnskey_data([apps.epp_api.SecDNSKeyData(
            flags=int(request.POST.get('flags')),
            protocol=int(request.POST.get('protocol')),
            algorithm=int(request.POST.get('algorithm')),
            public_key=request.POST.get('public_key'),
        )])
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    return redirect(referrer)


@login_required
def delete_domain_sec_dns(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    try:
        domain_data.del_secdns_all()
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    return redirect(referrer)


@login_required
def delete_domain_host_obj(request, domain_id, host_name):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_data = apps.epp_client.get_domain(user_domain.domain)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    if host_name == "all":
        host_objs = []
        for ns in domain_data.name_servers:
            if ns.host_obj:
                host_objs.append(ns.host_obj)
    else:
        host_objs = [host_name]

    try:
        domain_data.del_host_objs(host_objs)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    return redirect(referrer)


@login_required
def domain_hexdns(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_jwt = jwt.encode({
        "iat": datetime.datetime.utcnow(),
        "nbf": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        "iss": "urn:as207960:domains",
        "aud": ["urn:as207960:hexdns"],
        "domain": user_domain.domain,
        "sub": request.user.username,
    }, settings.JWT_PRIV_KEY, algorithm='ES384').decode()

    return redirect(f"{settings.HEXDNS_URL}/setup_domains_zone/?domain_token={domain_jwt}")


def domain_search(request):
    error = None

    if request.method == "POST":
        form = forms.DomainSearchForm(request.POST)
        if form.is_valid():
            try:
                domain_idna = form.cleaned_data['domain'].encode('idna').decode()
            except UnicodeError as e:
                form.add_error('domain', f"Invalid Unicode: {e}")
            else:
                zone, sld = zone_info.get_domain_info(domain_idna)
                if zone:
                    pending_domain = models.DomainRegistration.objects.filter(
                        domain=form.cleaned_data['domain']
                    ).first()
                    if pending_domain:
                        form.add_error('domain', "Domain unavailable")
                    else:
                        try:
                            available, reason, _ = apps.epp_client.check_domain(domain_idna)
                        except grpc.RpcError as rpc_error:
                            error = rpc_error.details()
                        else:
                            if not available:
                                if not reason:
                                    form.add_error('domain', "Domain unavailable")
                                else:
                                    form.add_error('domain', f"Domain unavailable: {reason}")
                            else:
                                if request.user.is_authenticated:
                                    return redirect('domain_register', domain_idna)
                                else:
                                    return redirect('domain_search_success', domain_idna)
                else:
                    form.add_error('domain', "Unsupported or invalid domain")
    else:
        form = forms.DomainSearchForm(initial={
            "domain": request.GET.get("domain")
        })

    return render(request, "domains/domain_search.html", {
        "domain_form": form,
        "error": error
    })


def domain_search_success(request, domain_name):
    return render(request, "domains/domain_search_success.html", {
        "domain": domain_name,
    })


@login_required
def domain_register(request, domain_name):
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)

    if not settings.REGISTRATION_ENABLED or not models.DomainRegistrationOrder.has_class_scope(access_token, 'create'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    user_addresses = models.Contact.get_object_list(access_token)
    user_contacts = models.ContactAddress.get_object_list(access_token)
    if not user_contacts.count() or not user_addresses.count():
        request.session["after_setup_uri"] = request.get_full_path()
        return render(request, "domains/domain_create_contact.html")

    error = None

    zone, sld = zone_info.get_domain_info(domain_name)
    if not zone:
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_unicode = domain_name.encode().decode('idna')
    except UnicodeError:
        domain_unicode = domain_name

    zone_price, registry_name, zone_notice = zone.pricing, zone.registry, zone.notice
    price_decimal = zone_price.representative_registration()

    if request.method == "POST":
        form = forms.DomainRegisterForm(
            request.POST,
            zone=zone,
            user=request.user
        )
        if form.is_valid():
            registrant = form.cleaned_data['registrant']
            admin_contact = form.cleaned_data['admin']
            billing_contact = form.cleaned_data['billing']
            tech_contact = form.cleaned_data['tech']
            period = form.cleaned_data['period']

            billing_value = zone_price.registration(sld, unit=period.unit, value=period.value)
            if billing_value is None:
                return render(request, "domains/error.html", {
                    "error": "You don't have permission to perform this action",
                    "back_url": referrer
                })

            order = models.DomainRegistrationOrder(
                domain=domain_name,
                period_unit=period.unit,
                period_value=period.value,
                registrant_contact=registrant,
                admin_contact=admin_contact,
                billing_contact=billing_contact,
                tech_contact=tech_contact,
                user=request.user,
                price=billing_value,
                auth_info=models.make_secret(),
                off_session=False,
            )
            order.save()
            tasks.process_domain_registration.delay(order.id)
            return redirect('domain_register_confirm', order.id)
    else:
        form = forms.DomainRegisterForm(
            zone=zone,
            user=request.user
        )

    return render(request, "domains/domain_form.html", {
        "domain_form": form,
        "domain_name": domain_unicode,
        "price_decimal": price_decimal,
        "zone_notice": zone_notice,
        "currency": zone_price.currency,
        "zone_info": zone,
        "error": error
    })


def confirm_order(request, order, confirm_template, pending_template):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    referrer = reverse('domains')

    if not order.has_scope(access_token, 'edit'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    if order.state == order.STATE_PENDING:
        if request.method == "POST":
            if request.POST.get("order") == "true":
                order.state = order.STATE_STARTED
                order.save()

                return render(request, "domains/domain_order_processing.html", {
                    "domain_name": order.domain
                })
            elif request.POST.get("order") == "false":
                order.state = order.STATE_FAILED
                order.save()
                return redirect(referrer)

        return render(request, confirm_template, {
            "domain": order.unicode_domain,
            "price_decimal": order.price,
        })

    if order.state == order.STATE_NEEDS_PAYMENT:
        if "charge_state_id" in request.GET:
            return render(request, "domains/domain_order_processing.html", {
                "domain_name": order.unicode_domain
            })
        return redirect(order.redirect_uri)
    elif order.state == order.STATE_PENDING_APPROVAL:
        return render(request, pending_template, {
            "domain_name": order.unicode_domain
        })
    elif order.state == order.STATE_FAILED:
        return render(request, "domains/error.html", {
            "error": order.last_error,
            "back_url": referrer
        })
    elif order.state == order.STATE_COMPLETED:
        return redirect('domain', order.domain_obj.id)
    else:
        return render(request, "domains/domain_order_processing.html", {
            "domain_name": order.unicode_domain
        })


@login_required
def domain_register_confirm(request, order_id):
    registration_order = get_object_or_404(models.DomainRegistrationOrder, id=order_id)

    return confirm_order(
        request, registration_order, "domains/register_domain_confirm.html", "domains/domain_pending.html"
    )


@login_required
def delete_domain(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'delete'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    domain_info = zone_info.get_domain_info(user_domain.domain)[0]

    can_delete = True

    if request.method == "POST":
        if can_delete and request.POST.get("delete") == "true":
            try:
                pending, registry_name, _transaction_id, _fee_data = apps.epp_client.delete_domain(user_domain.domain)
            except grpc.RpcError as rpc_error:
                error = rpc_error.details()
                return render(request, "domains/error.html", {
                    "error": error,
                    "back_url": referrer
                })

            gchat_bot.notify_delete.delay(user_domain.id, registry_name)
            if not domain_info.restore_supported:
                user_domain.delete()
            else:
                user_domain.deleted = True
                user_domain.save()
            return redirect('domains')

    return render(request, "domains/delete_domain.html", {
        "domain": user_domain,
        "can_delete": can_delete,
        "back_url": referrer
    })


@login_required
def renew_domain(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=False)

    if not user_domain.has_scope(access_token, 'edit') or \
            not models.DomainRenewOrder.has_class_scope(access_token, 'create'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    zone, sld = zone_info.get_domain_info(user_domain.domain)
    if not zone:
        raise Http404

    zone_price, _ = zone.pricing, zone.registry
    price_decimal = zone_price.representative_renewal()

    if request.method == "POST":
        form = forms.DomainRenewForm(
            request.POST,
            zone_info=zone
        )

        if form.is_valid():
            period = form.cleaned_data['period']

            period = apps.epp_api.Period(
                value=period.value,
                unit=period.unit
            )

            billing_value = zone_price.renewal(sld, unit=period.unit, value=period.value)
            if billing_value is None:
                return render(request, "domains/error.html", {
                    "error": "You don't have permission to perform this action",
                    "back_url": referrer
                })

            order = models.DomainRenewOrder(
                domain=user_domain.domain,
                domain_obj=user_domain,
                period_unit=period.unit,
                period_value=period.value,
                user=request.user,
                price=billing_value,
                off_session=False,
            )
            order.save()
            tasks.process_domain_renewal.delay(order.id)

            return redirect('renew_domain_confirm', order.id)
    else:
        form = forms.DomainRenewForm(zone_info=zone)

    return render(request, "domains/renew_domain.html", {
        "domain": user_domain,
        "domain_name": user_domain.domain,
        "zone_info": zone,
        "domain_form": form,
        "price_decimal": price_decimal,
        "currency": zone_price.currency,
    })


@login_required
def renew_domain_confirm(request, order_id):
    renew_order = get_object_or_404(models.DomainRenewOrder, id=order_id)

    return confirm_order(request, renew_order, "domains/renew_domain_confirm.html", "domains/domain_pending.html")


@login_required
def restore_domain(request, domain_id):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    user_domain = get_object_or_404(models.DomainRegistration, id=domain_id, deleted=True)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not user_domain.has_scope(access_token, 'edit') or \
            not models.DomainRestoreOrder.has_class_scope(access_token, 'create'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    zone, sld = zone_info.get_domain_info(user_domain.domain)
    if not zone:
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    zone_price, _ = zone.pricing, zone.registry
    billing_value = zone_price.restore(sld)

    order = models.DomainRestoreOrder(
        domain=user_domain.domain,
        domain_obj=user_domain,
        price=billing_value,
        user=request.user,
        off_session=False,
    )
    order.save()
    tasks.process_domain_restore.delay(order.id)

    return redirect('restore_domain_confirm', order.id)


@login_required
def restore_domain_confirm(request, order_id):
    restore_order = get_object_or_404(models.DomainRestoreOrder, id=order_id)

    return confirm_order(request, restore_order, "domains/restore_domain.html", "domains/domain_restore_pending.html")


def domain_transfer_query(request):
    error = None

    if request.method == "POST":
        form = forms.DomainSearchForm(request.POST)
        form.helper.form_action = request.get_full_path()

        if form.is_valid():
            try:
                domain_idna = idna.encode(form.cleaned_data['domain'], uts46=True).decode()
            except idna.IDNAError as e:
                form.add_error('domain', f"Invalid Unicode: {e}")
            else:
                zone, sld = zone_info.get_domain_info(domain_idna)
                if zone:
                    if not zone.transfer_supported:
                        form.add_error('domain', "Extension not yet supported for transfers")
                    else:
                        try:
                            if zone.pre_transfer_query_supported:
                                available, _, _ = apps.epp_client.check_domain(domain_idna)
                            else:
                                available = True
                        except grpc.RpcError as rpc_error:
                            error = rpc_error.details()
                        else:
                            if not available:
                                if zone.pre_transfer_query_supported:
                                    try:
                                        domain_data = apps.epp_client.get_domain(domain_idna)
                                    except grpc.RpcError as rpc_error:
                                        error = rpc_error.details()
                                    else:
                                        if any(s in domain_data.statuses for s in (3, 7, 8, 10, 15)):
                                            available = False
                                            form.add_error('domain', "Domain not eligible for transfer")

                            if available:
                                if request.user.is_authenticated:
                                    return redirect('domain_transfer', domain_idna)
                                else:
                                    return redirect('domain_transfer_search_success', domain_idna)
                            else:
                                form.add_error('domain', "Domain does not exist")
                else:
                    form.add_error('domain', "Unsupported or invalid domain")
    else:
        form = forms.DomainSearchForm()
        form.helper.form_action = request.get_full_path()

    return render(request, "domains/domain_transfer_query.html", {
        "domain_form": form,
        "error": error
    })


def domain_transfer_search_success(request, domain_name):
    return render(request, "domains/domain_transfer_search_success.html", {
        "domain": domain_name,
    })


@login_required
def domain_transfer(request, domain_name):
    access_token = django_keycloak_auth.clients.get_active_access_token(oidc_profile=request.user.oidc_profile)
    referrer = request.META.get("HTTP_REFERER")
    referrer = referrer if referrer else reverse('domains')

    if not settings.REGISTRATION_ENABLED or not models.DomainTransferOrder.has_class_scope(access_token, 'create'):
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    user_addresses = models.Contact.get_object_list(access_token)
    user_contacts = models.ContactAddress.get_object_list(access_token)
    if not user_contacts.count() or not user_addresses.count():
        request.session["after_setup_uri"] = request.get_full_path()
        return render(request, "domains/domain_create_contact.html")

    error = None

    zone, sld = zone_info.get_domain_info(domain_name)
    if not zone or not zone.transfer_supported:
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    try:
        domain_unicode = idna.decode(domain_name, uts46=True)
    except idna.IDNAError:
        return render(request, "domains/error.html", {
            "error": "You don't have permission to perform this action",
            "back_url": referrer
        })

    zone_price, registry_name = zone.pricing, zone.registry
    try:
        price_decimal = zone_price.transfer(sld)
    except grpc.RpcError as rpc_error:
        error = rpc_error.details()
        return render(request, "domains/error.html", {
            "error": error,
            "back_url": referrer
        })

    if request.method == "POST":
        form = forms.DomainTransferForm(request.POST, zone=zone, user=request.user)

        if form.is_valid():
            registrant = form.cleaned_data['registrant']  # type: models.Contact
            admin_contact = form.cleaned_data['admin']  # type: models.Contact
            tech_contact = form.cleaned_data['tech']  # type: models.Contact
            billing_contact = form.cleaned_data['billing']  # type: models.Contact

            order = models.DomainTransferOrder(
                domain=domain_name,
                auth_code=form.cleaned_data['auth_code'],
                registrant_contact=registrant,
                admin_contact=admin_contact,
                billing_contact=billing_contact,
                tech_contact=tech_contact,
                price=price_decimal,
                user=request.user,
                off_session=False,
            )
            order.save()
            tasks.process_domain_transfer.delay(order.id)

            return redirect('domain_transfer_confirm', order.id)
    else:
        form = forms.DomainTransferForm(zone=zone, user=request.user)

    return render(request, "domains/domain_transfer.html", {
        "domain_form": form,
        "domain_name": domain_unicode,
        "price_decimal": price_decimal,
        "zone_info": zone,
        "error": error
    })


@login_required
def domain_transfer_confirm(request, order_id):
    transfer_order = get_object_or_404(models.DomainTransferOrder, id=order_id)

    return confirm_order(
        request, transfer_order, "domains/transfer_domain_confirm.html", "domains/domain_transfer_pending.html"
    )


@require_POST
def internal_check_price(request):
    search_action = request.POST.get("action")
    search_domain = request.POST.get("domain")
    if not search_domain or not search_action:
        return HttpResponseBadRequest()

    domain_info, sld = zone_info.get_domain_info(search_domain)
    if not domain_info:
        return HttpResponseBadRequest()

    if search_action == "register":
        price = domain_info.pricing.registration(sld)
    else:
        return HttpResponseBadRequest()

    return HttpResponse(json.dumps({
        "price": float(price),
        "message": domain_info.notice
    }), content_type="application/json")
