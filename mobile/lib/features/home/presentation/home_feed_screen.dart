import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../favorites/data/favorites_repository.dart';
import '../../listings/data/categories_repository.dart';
import '../../listings/data/listings_repository.dart';
import '../../listings/presentation/widgets/listing_card.dart';
import '../../notifications/data/notifications_repository.dart';

class HomeFeedScreen extends ConsumerStatefulWidget {
  const HomeFeedScreen({super.key});

  @override
  ConsumerState<HomeFeedScreen> createState() => _HomeFeedScreenState();
}

class _HomeFeedScreenState extends ConsumerState<HomeFeedScreen> {
  final _searchCtrl = TextEditingController();

  List<dynamic> _listings = [];
  List<dynamic> _categories = [];
  final Set<int> _favoriteIds = <int>{};
  final Set<int> _favoriteBusyIds = <int>{};

  bool _loading = true;
  String? _error;
  int _page = 1;
  int _totalPages = 1;
  int _unreadNotifications = 0;

  int? _selectedCategoryId;
  String? _selectedCity;
  double? _minPrice;
  double? _maxPrice;
  String _sortBy = 'newest';

  @override
  void initState() {
    super.initState();
    _loadListings();
    _loadCategories();
    _loadFavoriteIds();
    _loadUnreadCount();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  bool get _hasSearchCriteria {
    return _searchCtrl.text.trim().isNotEmpty ||
        _selectedCategoryId != null ||
        (_selectedCity != null && _selectedCity!.trim().isNotEmpty) ||
        _minPrice != null ||
        _maxPrice != null ||
        _sortBy != 'newest';
  }

  Future<void> _loadListings({bool append = false}) async {
    if (!append) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final repo = ref.read(listingsRepositoryProvider);
      final data = await repo.getListings(
        page: _page,
        pageSize: 20,
        query: _searchCtrl.text.trim().isNotEmpty
            ? _searchCtrl.text.trim()
            : null,
        categoryId: _selectedCategoryId,
        city: _selectedCity,
        minPrice: _minPrice,
        maxPrice: _maxPrice,
        status: 'published',
        sortBy: _sortBy,
      );
      final items = data['items'] is List
          ? List<dynamic>.from(data['items'] as List)
          : <dynamic>[];
      final totalPages = (data['total_pages'] as num?)?.toInt() ?? 1;

      if (!mounted) {
        return;
      }

      setState(() {
        if (append) {
          _listings.addAll(items);
        } else {
          _listings = items;
        }
        _totalPages = totalPages;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _loadCategories() async {
    try {
      final cats = await ref
          .read(categoriesRepositoryProvider)
          .getCategories(activeOnly: true);
      if (!mounted) {
        return;
      }
      setState(() {
        _categories = cats;
      });
    } catch (_) {}
  }

  Future<void> _refresh() async {
    _page = 1;
    await Future.wait([
      _loadListings(),
      _loadFavoriteIds(),
      _loadUnreadCount(),
    ]);
  }

  void _loadMore() {
    if (_page < _totalPages) {
      _page++;
      _loadListings(append: true);
    }
  }

  void _applySearch() {
    _page = 1;
    _loadListings();
  }

  void _clearSearch() {
    setState(() {
      _searchCtrl.clear();
      _selectedCategoryId = null;
      _selectedCity = null;
      _minPrice = null;
      _maxPrice = null;
      _sortBy = 'newest';
    });
    _applySearch();
  }

  void _showFilterSheet() {
    final l = S.of(context)!;
    final minCtrl = TextEditingController(text: _minPrice?.toStringAsFixed(0));
    final maxCtrl = TextEditingController(text: _maxPrice?.toStringAsFixed(0));
    final cityCtrl = TextEditingController(text: _selectedCity);
    int? tempCatId = _selectedCategoryId;
    String tempSort = _sortBy;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTheme.bgMuted,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            20,
            20,
            MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      l.filters,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        setSheetState(() {
                          tempCatId = null;
                          tempSort = 'newest';
                          minCtrl.clear();
                          maxCtrl.clear();
                          cityCtrl.clear();
                        });
                      },
                      child: Text(l.reset),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  l.category,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    ChoiceChip(
                      label: Text(l.allCategories),
                      selected: tempCatId == null,
                      onSelected: (_) => setSheetState(() => tempCatId = null),
                    ),
                    ..._categories.map((cat) {
                      final id = cat['id'] as int;
                      final name = cat['name'] as String;
                      return ChoiceChip(
                        label: Text(name),
                        selected: tempCatId == id,
                        onSelected: (_) => setSheetState(() => tempCatId = id),
                      );
                    }),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  l.city,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 6),
                TextField(
                  controller: cityCtrl,
                  decoration: InputDecoration(hintText: l.city),
                ),
                const SizedBox(height: 16),
                Text(
                  l.price,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: minCtrl,
                        keyboardType: TextInputType.number,
                        decoration: InputDecoration(hintText: l.minPrice),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: maxCtrl,
                        keyboardType: TextInputType.number,
                        decoration: InputDecoration(hintText: l.maxPrice),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  l.sort,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    for (final entry in {
                      'newest': l.newest,
                      'oldest': l.oldest,
                      'price_asc': l.priceAsc,
                      'price_desc': l.priceDesc,
                      'most_viewed': l.mostViewed,
                    }.entries)
                      ChoiceChip(
                        label: Text(entry.value),
                        selected: tempSort == entry.key,
                        onSelected: (_) =>
                            setSheetState(() => tempSort = entry.key),
                      ),
                  ],
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      _selectedCategoryId = tempCatId;
                      _selectedCity = cityCtrl.text.trim().isNotEmpty
                          ? cityCtrl.text.trim()
                          : null;
                      _minPrice = double.tryParse(minCtrl.text);
                      _maxPrice = double.tryParse(maxCtrl.text);
                      _sortBy = tempSort;
                    });

                    Navigator.pop(ctx);
                    _applySearch();
                  },
                  child: Text(l.apply),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _loadFavoriteIds() async {
    try {
      final ids = await ref
          .read(favoritesRepositoryProvider)
          .fetchFavoriteIds();
      if (!mounted) {
        return;
      }
      setState(() {
        _favoriteIds
          ..clear()
          ..addAll(ids);
      });
    } catch (_) {}
  }

  Future<void> _loadUnreadCount() async {
    try {
      final data = await ref
          .read(notificationsRepositoryProvider)
          .getUnreadCount();
      final count = (data['unread_count'] as num?)?.toInt() ?? 0;
      if (!mounted) {
        return;
      }
      setState(() {
        _unreadNotifications = count;
      });
    } catch (_) {}
  }

  Future<void> _openListingDetails(int listingId) async {
    await context.push('/listing/$listingId');
    if (!mounted) {
      return;
    }
    await _loadFavoriteIds();
  }

  Future<void> _toggleFavorite(int listingId) async {
    if (_favoriteBusyIds.contains(listingId)) {
      return;
    }

    final wasFavorite = _favoriteIds.contains(listingId);
    setState(() {
      _favoriteBusyIds.add(listingId);
      if (wasFavorite) {
        _favoriteIds.remove(listingId);
      } else {
        _favoriteIds.add(listingId);
      }
    });

    try {
      final repo = ref.read(favoritesRepositoryProvider);
      if (wasFavorite) {
        await repo.removeFavorite(listingId);
      } else {
        await repo.addFavorite(listingId);
      }
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        if (wasFavorite) {
          _favoriteIds.add(listingId);
        } else {
          _favoriteIds.remove(listingId);
        }
      });
    } finally {
      if (mounted) {
        setState(() {
          _favoriteBusyIds.remove(listingId);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: const Text('KM-M'),
        actions: [
          IconButton(
            icon: const Icon(Icons.storefront_outlined),
            tooltip: l.myListings,
            onPressed: () => context.push('/my-listings'),
          ),
          IconButton(
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_outlined),
                if (_unreadNotifications > 0)
                  Positioned(
                    right: -2,
                    top: -2,
                    child: Container(
                      constraints: const BoxConstraints(minWidth: 16),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 1,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.accent,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        _unreadNotifications > 99
                            ? '99+'
                            : '$_unreadNotifications',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            onPressed: () async {
              await context.push('/notifications');
              if (mounted) {
                _loadUnreadCount();
              }
            },
          ),
        ],
      ),
      body: _buildBody(l),
    );
  }

  Widget _buildBody(S l) {
    final listingsRepo = ref.read(listingsRepositoryProvider);

    return Column(
      children: [
        _buildSearchSection(l),
        Expanded(child: _buildListingsContent(l, listingsRepo)),
      ],
    );
  }

  Widget _buildSearchSection(S l) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: l.search,
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchCtrl.text.trim().isEmpty
                        ? null
                        : IconButton(
                            onPressed: () {
                              setState(() {
                                _searchCtrl.clear();
                              });
                              _applySearch();
                            },
                            icon: const Icon(Icons.close, size: 18),
                          ),
                    contentPadding: const EdgeInsets.symmetric(
                      vertical: 10,
                      horizontal: 12,
                    ),
                    isDense: true,
                  ),
                  textInputAction: TextInputAction.search,
                  onChanged: (_) => setState(() {}),
                  onSubmitted: (_) => _applySearch(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: _showFilterSheet,
                icon: const Icon(Icons.tune, size: 20),
                style: IconButton.styleFrom(
                  backgroundColor: AppTheme.accent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppTheme.radius),
                  ),
                ),
              ),
            ],
          ),
          if (_hasSearchCriteria)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _clearSearch,
                icon: const Icon(Icons.restart_alt, size: 18),
                label: Text(l.reset),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildListingsContent(S l, ListingsRepository listingsRepo) {
    if (_loading && _listings.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _listings.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(
              l.errorOccurred,
              style: const TextStyle(color: AppTheme.textSubtle),
            ),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _refresh, child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_listings.isEmpty) {
      final emptyText = _hasSearchCriteria ? l.noResults : l.emptyList;
      final emptyIcon = _hasSearchCriteria
          ? Icons.search_off
          : Icons.home_outlined;

      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(emptyIcon, size: 64, color: AppTheme.textSubtle),
            const SizedBox(height: 12),
            Text(
              emptyText,
              style: const TextStyle(color: AppTheme.textSubtle, fontSize: 16),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _refresh,
      child: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification is ScrollEndNotification &&
              notification.metrics.extentAfter < 200) {
            _loadMore();
          }
          return false;
        },
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: GridView.builder(
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 0.68,
            ),
            itemCount: _listings.length,
            itemBuilder: (context, index) {
              final rawListing = _listings[index];
              if (rawListing is! Map) {
                return const SizedBox.shrink();
              }

              final listing = Map<String, dynamic>.from(rawListing);
              final listingId = (listing['id'] as num?)?.toInt() ?? 0;
              if (listingId <= 0) {
                return const SizedBox.shrink();
              }

              final thumbnailUrl = listingsRepo.extractThumbnailUrl(listing);
              final priceRaw = listing['price'];
              final price = (priceRaw is String)
                  ? double.tryParse(priceRaw) ?? 0
                  : (priceRaw as num?)?.toDouble() ?? 0;

              return ListingCard(
                id: listingId,
                title: listing['title']?.toString() ?? '-',
                price: price,
                currency: listing['currency']?.toString() ?? 'KGS',
                city: listing['city']?.toString() ?? '-',
                transactionType:
                    listing['transaction_type']?.toString() ?? 'sale',
                thumbnailUrl: thumbnailUrl,
                thumbnailUrlFuture: thumbnailUrl == null
                    ? listingsRepo.getPrimaryThumbnailUrl(listingId)
                    : null,
                isFavorite: _favoriteIds.contains(listingId),
                isPromoted: listing['is_subscription'] == true,
                onTap: () {
                  _openListingDetails(listingId);
                },
                onFavoriteTap: _favoriteBusyIds.contains(listingId)
                    ? null
                    : () => _toggleFavorite(listingId),
              );
            },
          ),
        ),
      ),
    );
  }
}
