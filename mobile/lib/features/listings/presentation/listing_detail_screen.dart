import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:latlong2/latlong.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../chat/data/chat_repository.dart';
import '../../favorites/data/favorites_repository.dart';
import '../../profile/data/profile_repository.dart';
import '../../reports/data/reports_repository.dart';
import '../data/listings_repository.dart';

class ListingDetailScreen extends ConsumerStatefulWidget {
  const ListingDetailScreen({super.key, required this.listingId});
  final int listingId;

  @override
  ConsumerState<ListingDetailScreen> createState() =>
      _ListingDetailScreenState();
}

class _ListingDetailScreenState extends ConsumerState<ListingDetailScreen> {
  Map<String, dynamic>? _listing;
  List<dynamic> _media = [];
  bool _loading = true;
  String? _error;
  int _currentImageIndex = 0;
  bool _openingConversation = false;
  bool _isFavorite = false;
  bool _updatingFavorite = false;
  int? _currentUserId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final repo = ref.read(listingsRepositoryProvider);
      final listing = await repo.getListing(widget.listingId);
      final media = await repo.getListingMedia(widget.listingId);
      final listingId = (listing['id'] as num?)?.toInt();
      int? currentUserId;

      var isFavorite = false;
      if (listingId != null) {
        try {
          final favoriteIds = await ref
              .read(favoritesRepositoryProvider)
              .fetchFavoriteIds(maxPages: 8);
          isFavorite = favoriteIds.contains(listingId);
        } catch (_) {}
      }

      try {
        final me = await ref.read(profileRepositoryProvider).getMyProfile();
        currentUserId = (me['id'] as num?)?.toInt();
      } catch (_) {}

      setState(() {
        _listing = listing;
        _media = media;
        _isFavorite = isFavorite;
        _currentUserId = currentUserId;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  String _formatPrice(dynamic price, String currency) {
    final value = (price is String)
        ? double.parse(price)
        : (price as num).toDouble();
    final intPrice = value.toInt();
    final buffer = StringBuffer();
    final str = intPrice.toString();
    for (var i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buffer.write(' ');
      buffer.write(str[i]);
    }
    return '$buffer $currency';
  }

  String _txLabel(String tx, S l) {
    switch (tx) {
      case 'sale':
        return l.sale;
      case 'rent_long':
        return l.rentLong;
      case 'rent_daily':
        return l.rentDaily;
      default:
        return tx;
    }
  }

  bool get _canPromote {
    final listing = _listing;
    if (listing == null) {
      return false;
    }

    final status = listing['status']?.toString();
    if (status != 'published') {
      return false;
    }

    final ownerId = (listing['owner_id'] as num?)?.toInt();
    return ownerId != null &&
        _currentUserId != null &&
        ownerId == _currentUserId;
  }

  Future<void> _openPromoteFlow() async {
    final listing = _listing;
    if (listing == null) {
      return;
    }

    final listingId = (listing['id'] as num?)?.toInt();
    if (listingId == null) {
      return;
    }

    await context.push('/promote/$listingId', extra: listing);
    if (!mounted) {
      return;
    }
    await _load();
  }

  Future<void> _openConversation() async {
    final listing = _listing;
    if (listing == null || _openingConversation) {
      return;
    }

    final l = S.of(context)!;
    final listingId = (listing['id'] as num?)?.toInt();
    if (listingId == null) {
      return;
    }

    setState(() {
      _openingConversation = true;
    });

    try {
      final conversation = await ref
          .read(chatRepositoryProvider)
          .openConversationForListing(listingId);

      if (!mounted) {
        return;
      }

      final conversationId = (conversation['id'] as num?)?.toInt();
      if (conversationId != null) {
        context.push('/chat/$conversationId', extra: conversation);
      }
    } on DioException catch (e) {
      if (!mounted) {
        return;
      }

      final data = e.response?.data;
      var message = l.errorOccurred;
      if (data is Map && data['detail'] is String) {
        message = data['detail'].toString();
      } else if (e.message != null && e.message!.trim().isNotEmpty) {
        message = e.message!;
      }

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    } finally {
      if (mounted) {
        setState(() {
          _openingConversation = false;
        });
      }
    }
  }

  Future<void> _toggleFavorite() async {
    final listing = _listing;
    if (listing == null || _updatingFavorite) {
      return;
    }

    final listingId = (listing['id'] as num?)?.toInt();
    if (listingId == null) {
      return;
    }

    final l = S.of(context)!;
    final wasFavorite = _isFavorite;

    setState(() {
      _updatingFavorite = true;
      _isFavorite = !wasFavorite;
    });

    try {
      final repo = ref.read(favoritesRepositoryProvider);
      final data = wasFavorite
          ? await repo.removeFavorite(listingId)
          : await repo.addFavorite(listingId);

      final nextFavoriteCount = (data['favorite_count'] as num?)?.toInt();
      if (nextFavoriteCount != null && _listing != null) {
        final next = Map<String, dynamic>.from(_listing!);
        next['favorite_count'] = nextFavoriteCount;
        setState(() {
          _listing = next;
        });
      }
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _isFavorite = wasFavorite;
      });

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    } finally {
      if (mounted) {
        setState(() {
          _updatingFavorite = false;
        });
      }
    }
  }

  Future<void> _showReportSheet() async {
    final listing = _listing;
    if (listing == null) {
      return;
    }

    final listingId = (listing['id'] as num?)?.toInt();
    if (listingId == null) {
      return;
    }

    final l = S.of(context)!;
    final reasonCtrl = TextEditingController();
    var selectedReason = 'spam';
    var submitting = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (sheetContext, setSheetState) {
            final reasons = <String, String>{
              'spam': l.spam,
              'fake_listing': l.fakeListing,
              'scam': l.scam,
              'duplicate': l.duplicate,
              'offensive': l.offensive,
              'prohibited': l.prohibited,
              'other': l.other,
            };

            return Padding(
              padding: EdgeInsets.fromLTRB(
                16,
                16,
                16,
                MediaQuery.of(sheetContext).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    l.reportListing,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedReason,
                    decoration: InputDecoration(labelText: l.reportReason),
                    items: reasons.entries
                        .map(
                          (entry) => DropdownMenuItem<String>(
                            value: entry.key,
                            child: Text(entry.value),
                          ),
                        )
                        .toList(),
                    onChanged: submitting
                        ? null
                        : (value) {
                            if (value == null) {
                              return;
                            }
                            setSheetState(() {
                              selectedReason = value;
                            });
                          },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: reasonCtrl,
                    maxLines: 3,
                    enabled: !submitting,
                    decoration: InputDecoration(labelText: l.description),
                  ),
                  const SizedBox(height: 14),
                  ElevatedButton(
                    onPressed: submitting
                        ? null
                        : () async {
                            final messenger = ScaffoldMessenger.of(context);

                            setSheetState(() {
                              submitting = true;
                            });

                            try {
                              final text = reasonCtrl.text.trim();
                              await ref
                                  .read(reportsRepositoryProvider)
                                  .createReport(
                                    targetType: 'listing',
                                    targetId: listingId,
                                    reasonCode: selectedReason,
                                    reasonText: text.isEmpty ? null : text,
                                  );

                              if (!context.mounted) {
                                return;
                              }

                              if (sheetContext.mounted) {
                                Navigator.pop(sheetContext);
                              }
                              messenger.showSnackBar(
                                SnackBar(content: Text(l.reportSubmitted)),
                              );
                            } on DioException catch (e) {
                              final data = e.response?.data;
                              var message = l.errorOccurred;
                              if (data is Map && data['detail'] is String) {
                                message = data['detail'].toString();
                              }
                              if (context.mounted) {
                                messenger.showSnackBar(
                                  SnackBar(content: Text(message)),
                                );
                              }
                            } catch (_) {
                              if (context.mounted) {
                                messenger.showSnackBar(
                                  SnackBar(content: Text(l.errorOccurred)),
                                );
                              }
                            } finally {
                              if (sheetContext.mounted) {
                                setSheetState(() {
                                  submitting = false;
                                });
                              }
                            }
                          },
                    child: submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(l.apply),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    reasonCtrl.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    if (_loading) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null || _listing == null) {
      return Scaffold(
        appBar: AppBar(),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.error_outline,
                size: 48,
                color: AppTheme.textSubtle,
              ),
              const SizedBox(height: 12),
              Text(l.errorOccurred),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _load, child: Text(l.retry)),
            ],
          ),
        ),
      );
    }

    final listing = _listing!;
    final lat = double.tryParse(listing['latitude'].toString()) ?? 0;
    final lng = double.tryParse(listing['longitude'].toString()) ?? 0;
    final repo = ref.read(listingsRepositoryProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          // Image gallery
          SliverAppBar(
            expandedHeight: 300,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              background: _media.isNotEmpty
                  ? PageView.builder(
                      itemCount: _media.length,
                      onPageChanged: (i) =>
                          setState(() => _currentImageIndex = i),
                      itemBuilder: (_, i) {
                        final item = _media[i] as Map<String, dynamic>;
                        final mediaId = item['id'] as int;
                        return CachedNetworkImage(
                          imageUrl: repo.fullImageUrl(mediaId),
                          fit: BoxFit.cover,
                          placeholder: (context, url) =>
                              Container(color: AppTheme.bgMuted),
                          errorWidget: (context, url, error) => Container(
                            color: AppTheme.bgMuted,
                            child: const Icon(
                              Icons.broken_image,
                              size: 48,
                              color: AppTheme.textSubtle,
                            ),
                          ),
                        );
                      },
                    )
                  : Container(
                      color: AppTheme.bgMuted,
                      child: const Icon(
                        Icons.apartment_rounded,
                        size: 64,
                        color: AppTheme.textSubtle,
                      ),
                    ),
            ),
            actions: [
              IconButton(
                icon: Icon(
                  _isFavorite ? Icons.favorite : Icons.favorite_border,
                  color: _isFavorite ? Colors.redAccent : null,
                ),
                tooltip: _isFavorite ? l.removeFromFavorites : l.addToFavorites,
                onPressed: _updatingFavorite ? null : _toggleFavorite,
              ),
              PopupMenuButton<String>(
                onSelected: (value) {
                  if (value == 'report') {
                    _showReportSheet();
                  }
                },
                itemBuilder: (_) => [
                  PopupMenuItem(value: 'report', child: Text(l.reportListing)),
                ],
              ),
            ],
          ),

          // Image indicator
          if (_media.length > 1)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    _media.length,
                    (i) => Container(
                      width: 7,
                      height: 7,
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i == _currentImageIndex
                            ? AppTheme.accent
                            : AppTheme.border,
                      ),
                    ),
                  ),
                ),
              ),
            ),

          // Content
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Price + type
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          _formatPrice(
                            listing['price'],
                            listing['currency'] as String,
                          ),
                          style: const TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          color: AppTheme.accent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          _txLabel(listing['transaction_type'] as String, l),
                          style: const TextStyle(
                            color: AppTheme.accent,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Title
                  Text(
                    listing['title'] as String,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 6),

                  // City
                  Row(
                    children: [
                      const Icon(
                        Icons.location_on_outlined,
                        size: 16,
                        color: AppTheme.textSubtle,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        listing['city'] as String,
                        style: const TextStyle(
                          color: AppTheme.textSubtle,
                          fontSize: 14,
                        ),
                      ),
                      if (listing['address_line'] != null) ...[
                        const Text(
                          ' · ',
                          style: TextStyle(color: AppTheme.textSubtle),
                        ),
                        Expanded(
                          child: Text(
                            listing['address_line'] as String,
                            style: const TextStyle(
                              color: AppTheme.textSubtle,
                              fontSize: 14,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${listing['view_count']} views · ${listing['favorite_count']} favorites',
                    style: const TextStyle(
                      color: AppTheme.textSubtle,
                      fontSize: 12,
                    ),
                  ),

                  const Divider(height: 32),

                  // Description
                  Text(
                    l.description,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    listing['description'] as String,
                    style: const TextStyle(fontSize: 14, height: 1.5),
                  ),

                  // Dynamic attributes
                  if (listing['dynamic_attributes'] != null &&
                      (listing['dynamic_attributes'] as Map).isNotEmpty) ...[
                    const Divider(height: 32),
                    ...((listing['dynamic_attributes'] as Map<String, dynamic>)
                        .entries
                        .map(
                          (e) => Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(
                              children: [
                                Text(
                                  '${e.key}: ',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 14,
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    '${e.value}',
                                    style: const TextStyle(fontSize: 14),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        )),
                  ],

                  const Divider(height: 32),

                  // Map
                  Text(
                    l.viewOnMap,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 200,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                      child: FlutterMap(
                        options: MapOptions(
                          initialCenter: LatLng(lat, lng),
                          initialZoom: 15,
                          interactionOptions: const InteractionOptions(
                            flags: InteractiveFlag.none,
                          ),
                        ),
                        children: [
                          TileLayer(
                            urlTemplate:
                                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                            userAgentPackageName: 'kg.demo.km_marketplace',
                          ),
                          MarkerLayer(
                            markers: [
                              Marker(
                                point: LatLng(lat, lng),
                                width: 40,
                                height: 40,
                                child: const Icon(
                                  Icons.location_pin,
                                  color: AppTheme.accent,
                                  size: 40,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (listing['map_address_label'] != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      listing['map_address_label'] as String,
                      style: const TextStyle(
                        color: AppTheme.textSubtle,
                        fontSize: 12,
                      ),
                    ),
                  ],

                  const Divider(height: 32),

                  // Owner card
                  GestureDetector(
                    onTap: () => context.push('/owner/${listing['owner_id']}'),
                    child: Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.bgMuted,
                        borderRadius: BorderRadius.circular(
                          AppTheme.cardRadius,
                        ),
                        border: Border.all(color: AppTheme.border),
                      ),
                      child: Row(
                        children: [
                          CircleAvatar(
                            radius: 24,
                            backgroundColor: AppTheme.accent,
                            child: Text(
                              '${listing['owner_id']}'.substring(0, 1),
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  l.ownerProfile,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 15,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  l.viewAllListings,
                                  style: const TextStyle(
                                    color: AppTheme.accent,
                                    fontSize: 13,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Icon(
                            Icons.chevron_right,
                            color: AppTheme.textSubtle,
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 80),
                ],
              ),
            ),
          ),
        ],
      ),
      // Bottom action bar
      bottomSheet: Container(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        decoration: const BoxDecoration(
          color: AppTheme.bgSurface,
          border: Border(top: BorderSide(color: AppTheme.border)),
        ),
        child: SafeArea(
          child: _canPromote
              ? ElevatedButton.icon(
                  onPressed: _openPromoteFlow,
                  icon: const Icon(Icons.bolt_outlined, size: 18),
                  label: Text(l.promote),
                )
              : ElevatedButton.icon(
                  onPressed: _openingConversation ? null : _openConversation,
                  icon: const Icon(Icons.chat_bubble_outline, size: 18),
                  label: _openingConversation
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(l.contactOwner),
                ),
        ),
      ),
    );
  }
}
